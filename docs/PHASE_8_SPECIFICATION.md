# VesselOptima — Phase 8: Scenario Analysis, Sensitivity & What-If Engine Specification

## 1. Subsystem Purpose & Scope

Phase 8 introduces **Scenario Analysis, Sensitivity & What-If Optimization** into VesselOptima:

> **Phase 7 answers:** *"What is the globally optimal fleet allocation under current baseline assumptions?"*  
> **Phase 8 answers:** *"How does the optimal fleet plan change when important market forecasts, bunker costs, freight rates, laycan timings, or vessel availabilities change?"*

### Fundamental Architectural Boundary
```text
Phases 1–6: Domain, Forecasts, Feasibility, Procurement, Idle & Candidates
      │
      ▼
Phase 7: Baseline MILP Optimization (Single Source of Truth for Allocation)
      │
      ▼ [Baseline Optimal Solution]
Phase 8: Scenario Engine (Copy-on-Scenario Parameter Transformations)
      │
      ├── Freight Rate Multipliers (+/-10%, +/-25%)
      ├── Bunker Price Multipliers (+10%, +25%, +50%)
      ├── Idle Holding Cost Multipliers (+10%, +25%, +50%)
      ├── Port Disbursement Multipliers (+/-20%)
      ├── Tightened Laycan Windows (Upstream Feasibility Revalidation)
      └── Fleet Availability Adjustments (Vessel Outage / Delay)
      │
      ▼
Phase 7 HiGHS MILP Re-Solve (Zero Duplication of Optimizer)
      │
      ▼
Scenario Outcome & Baseline Comparison
      │
      ├── Delta Metrics (Objective, Revenue, Cost, Contribution, Idle)
      ├── Assignment Difference Engine (UNCHANGED, ADDED, DROPPED, REPLACED)
      ├── One-Variable-at-a-Time (OVAT) Sensitivity Curves
      ├── Break-Even Switching Thresholds
      └── Scenario Robustness Scoring (% Stability across Stress Scenarios)
```

### Core Non-Negotiable Principles
1. **Single Source of Truth for Allocation**: Phase 8 **never** implements a second optimizer or greedy fallback. All scenario evaluations delegate directly to the Phase 7 HiGHS MILP engine (`OptimizationService`).
2. **Baseline Immutability**: Baseline candidates, master data, fixtures, and historical runs are never mutated. Copy-on-scenario semantics enforce `hash(baseline_before) == hash(baseline_after)`.
3. **Upstream Feasibility Integrity**: Operational adjustments (laycan tightening, vessel delays, vessel outages) re-validate against upstream physical and scheduling constraints.
4. **USD Currency Consistency**: Denominated strictly in USD.
5. **Air-Gap Guarantee**: 100% offline local execution with zero network calls.

---

## 2. Mathematical Formulation & Scenario Transformation Mechanics

### 2.1 Copy-on-Scenario Parameter Transformations
For each candidate $k \in \mathcal{K}$:
1. **Freight Adjustment**:
   $$R_k^{\prime} = R_k \cdot m_{\text{freight}}$$
2. **Bunker Adjustment**:
   $$C_{\text{bunker}, k}^{\prime} = C_{\text{bunker}, k} \cdot m_{\text{bunker}}$$
3. **Port Cost Adjustment**:
   $$C_{\text{port}, k}^{\prime} = C_{\text{port}, k} \cdot m_{\text{port}}$$
4. **Voyage Cost & Net Contribution**:
   $$C_k^{\prime} = C_{\text{operating}, k} + C_{\text{bunker}, k}^{\prime} + C_{\text{port}, k}^{\prime}$$
   $$P_k^{\prime} = R_k^{\prime} - C_k^{\prime}$$
5. **Idle Holding Rate Adjustment**:
   $$I_k^{\prime} = \text{idle\_days\_saved}_k \cdot (\text{DailyIdleRate}_k \cdot m_{\text{idle}})$$
6. **Laycan Tightening ($\Delta_{\text{laycan}}$ days)**:
   $$\text{LaycanEnd}^{\prime} = \text{LaycanEnd} - \Delta_{\text{laycan}}$$
   If presentation date $\text{Arrival}_k > \text{LaycanEnd}^{\prime}$:
   Candidate is marked `status = INFEASIBLE` with reason `LAYCAN_WINDOW_TIGHTENED_EXCEEDED` and excluded from the MILP.
7. **Vessel Availability Adjustments**:
   If vessel $v(k) \in \text{excluded\_vessel\_ids}$ or delayed beyond laycan, candidate is marked `status = INFEASIBLE` with reason `VESSEL_EXCLUDED_IN_SCENARIO` and excluded from the MILP.

### 2.2 Assignment Difference Engine
* **Candidate Decision Delta**:
  * $x_k^{\text{base}} = 1 \land x_k^{\text{scen}} = 1 \implies$ `UNCHANGED`
  * $x_k^{\text{base}} = 0 \land x_k^{\text{scen}} = 1 \implies$ `ADDED`
  * $x_k^{\text{base}} = 1 \land x_k^{\text{scen}} = 0 \implies$ `DROPPED`
  * $x_k^{\text{base}} = 0 \land x_k^{\text{scen}} = 0 \implies$ `REJECTED`
* **Cargo Allocation Delta**:
  * If assigned vessel $v_{\text{base}}(c) \neq v_{\text{scen}}(c)$ (both non-null) $\implies$ `REPLACED` ($v_{\text{base}} \to v_{\text{scen}}$)
  * If $v_{\text{base}}(c) \neq \text{None} \land v_{\text{scen}}(c) = \text{None} \implies$ `DROPPED_TO_UNSERVED`
  * If $v_{\text{base}}(c) = \text{None} \land v_{\text{scen}}(c) \neq \text{None} \implies$ `NEWLY_SERVED`
  * If $v_{\text{base}}(c) = v_{\text{scen}}(c) \implies$ `UNCHANGED`

### 2.3 Sensitivity & Robustness Analysis
* **One-Variable-at-a-Time (OVAT) Sweep**:
  Evaluates selected parameter over specified intervals (e.g. $[0.7\times, 1.5\times]$), re-solves MILP, and records objective curve and stability.
* **Break-Even Switching Threshold**:
  Identifies parameter values where cargo allocations flip or drop.
* **Robustness Score**:
  For an assignment $a$ across scenario ensemble $\mathcal{S}$:
  $$\text{Robustness}(a) = \frac{\sum_{s \in \mathcal{S}} \mathbb{I}(a \in \text{Selected}(s))}{|\mathcal{S}|} \times 100\%$$
  - **CORE ROBUST**: $\ge 80\%$
  - **CONDITIONALLY STABLE**: $50\% - 79\%$
  - **FRAGILE**: $< 50\%$
