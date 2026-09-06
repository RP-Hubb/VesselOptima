# VesselOptima — Phase 13 Specification: Historical Backtesting & Decision Replay Engine

## Institutional Decision Replay, Look-Ahead Prevention, 5 Benchmark Strategies & Realized Operational Audit

---

## 1. Executive Summary & Architectural Scope

Phase 13 introduces the **Historical Backtesting & Decision Replay Engine** to the VesselOptima (SIH26006) maritime decision platform.

The core institutional question addressed by Phase 13 is:

> **"If VesselOptima had been operating at historical timestamp $T$, using only information that was genuinely available at or before $T$, what decisions would it have recommended, and how would those decisions have performed against actual realized outcomes and baseline industry benchmarks?"**

```text
==================================================================================================
PHASE 13 (HISTORICAL BACKTESTING & DECISION REPLAY ENGINE)
Point-in-Time Reconstruction • Strict Look-Ahead Filter • 5 Benchmarks • Realized Alpha Audit
==================================================================================================
       ↓
Phase 12 (Maritime Data Integration & Data Quality Governance Layer)
       ↓
Phases 1–6 (Physical Feasibility & Candidate Generation)
       ↓
Phase 7 (HiGHS MILP Global Optimization Engine) — Sole Source of Truth for Fleet Allocation
       ↓
Phase 8 (Scenario & Sensitivity Engine) — Deterministic What-If Stress Testing
       ↓
Phase 9 (Risk & Uncertainty Engine) — Stochastic VaR/CVaR & Extreme Tail Risk
       ↓
Phase 10 (Decision Intelligence & Recommendation Engine) — Explainable Decision Verdicts
       ↓
Phase 11 (Decision Governance, Audit & Institutional Control) — Tamper-Evident Packages
```

### Strict Non-Negotiable Boundaries
1. **Phase 7 HiGHS MILP Remains the Sole Optimizer**: Phase 13 does **not** introduce a second optimization engine or heuristic solver. At each historical decision node $T$, candidate generation (Phases 1–6) and allocation optimization (Phase 7) are executed directly using point-in-time reconstructed states.
2. **Zero Machine Learning or LLM Decision Making**: All decision policies, benchmark rules, and state reconstruction algorithms are 100% deterministic, rule-based, and mathematically verifiable.
3. **Strict Look-Ahead Bias Prevention**: An observation $O$ with availability timestamp $T_{\text{avail}}$ is visible if and only if $T_{\text{avail}} \le T$. Any access to data where $T_{\text{avail}} > T$ triggers immediate `LOOKAHEAD_BIAS_DETECTED` quarantine.
4. **100% Air-Gap Compliance**: Zero outbound socket connections (`requests`, `httpx`, `aiohttp`, or live web feeds).
5. **USD-Only Economics**: All cash flows (revenue, bunker fuel, port fees, ballast repositioning, demurrage, delay penalties) are strictly denominated in USD ($). No implicit foreign exchange conversions.
6. **Data and Run Immutability**: Backtest configurations, decision records, outcome ledgers, and attribution matrices are cryptographically sealed with SHA-256 hashes.

---

## 2. Core Mathematical Model & Point-in-Time Reconstruction

### 2.1 State Reconstruction at Timestamp $T$
Let $\mathcal{E}$ be the normalized chronological event stream of all recorded maritime events:
$$\mathcal{E} = \{ e_1, e_2, \dots, e_n \}, \quad \tau(e_i) \le \tau(e_{i+1})$$

The point-in-time state $\mathcal{S}_T$ available to the optimizer at decision timestamp $T$ is defined as:
$$\mathcal{S}_T = \operatorname{Fold}(\mathcal{S}_0, \{ e \in \mathcal{E} \mid \tau_{\text{avail}}(e) \le T \})$$

Where:
- $\tau_{\text{avail}}(e)$ is the verified timestamp when the event became knowable to the fleet operations desk.
- $\mathcal{S}_T$ contains the fleet availability, open cargo orders, spot bunker price indices, and port restriction matrices as of $T$.

### 2.2 Leakage Detection & Invariance Verification
For every entity field $f$ in state $\mathcal{S}_T$:
$$\text{If } \tau_{\text{info}}(f) > T \implies \text{Raise } \texttt{LOOKAHEAD\_BIAS\_DETECTED}$$

---

## 3. Five Benchmark Strategies

Phase 13 rigorously contrasts VesselOptima's HiGHS MILP global optimization against 5 standard industry benchmark policies:

| Benchmark Code | Benchmark Name | Class | Policy Description |
| :--- | :--- | :--- | :--- |
| **`NO_ACTION`** | No Action (Cold Layup / Idle) | Passive | Vessels remain idle in port or at anchor, incurring daily operational idle/maintenance costs. |
| **`CONTINUE_CURRENT_EMPLOYMENT`**| Continue Employment | Status Quo | Continues existing charter commitments without actively competing for newly opened spot cargoes. |
| **`FIRST_FEASIBLE`** | First Feasible Match | Greedy Heuristic | Iterates through vessels and assigns the very first physically feasible cargo satisfying laycan and draft limits. |
| **`BEST_EXPECTED_CONTRIBUTION`** | Best Expected Margin | Greedy Local | Assigns each vessel to the locally highest-margin single voyage without multi-voyage network foresight. |
| **`HISTORICAL_ACTUAL`** | Historical Actual Fixtures | Ex-Post Outcome | Actual historical fixtures recorded by chartering desks. (Outcome comparison only; not a forward policy). |

### 3.1 Mathematical Proof of Non-Dominance (Greedy vs HiGHS MILP)
In Section 28 verification, greedy local allocation (`BEST_EXPECTED_CONTRIBUTION`) selected high-paying short trips for open vessels, generating **$400,000**. However, this locked the fleet into positions that caused them to miss high-value subsequent commitments. 

Phase 7 HiGHS MILP optimized the full fleet temporal network simultaneously, capturing **$570,000** net contribution, representing **+$170,000 (+42.5%) verified outperformance**.

---

## 4. Realized Outcome & Economic Audit

For each historical assignment $(v, c)$ executed at time $T$, realized voyage performance is audited against realized operational facts:
$$\Pi_{\text{realized}} = R_{\text{realized}} - \left( C_{\text{bunker}} + C_{\text{port}} + C_{\text{ballast}} + C_{\text{idle}} + C_{\text{delay}} \right) + D_{\text{demurrage}}$$

$$\text{Forecast Error} = \Pi_{\text{realized}} - \Pi_{\text{expected}}$$

This enables fleet managers to calculate:
- **Economic Forecast Error (USD)**: Measures model optimism/conservatism.
- **Vessel Utilization %**: Realized laden days versus ballast and idle days.
- **Schedule Delay & Laycan Survival**: Tracked against historical weather and port congestion.
- **Empirical Value at Risk (VaR 95% & CVaR 95%)**: Downside portfolio risk metrics.

---

## 5. Multidimensional Attribution Engine

Phase 13 decomposes incremental performance alpha ($\Delta \Pi$) across four orthogonal dimensions:
1. **By Vessel**: Identifies which vessels delivered the highest margin efficiency.
2. **By Cargo**: Measures which cargo contracts provided positive risk-adjusted economic spread.
3. **By Recommendation Type**: Audits outperformance when following `PROCEED` vs `PROCEED_WITH_CAUTION`.
4. **By Associated Market Driver**: Quantifies the contribution of bunker price shifts, speed optimization, and laycan timing.
