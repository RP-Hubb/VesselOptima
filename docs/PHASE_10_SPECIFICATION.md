# VesselOptima — Phase 10 Specification: Decision Intelligence & Explainable Recommendation Engine

## Transparent, Deterministic Decision Synthesis & Actionable Governance

---

## 1. Executive Summary & Architectural Scope

Phase 10 delivers the **Decision Intelligence & Explainable Recommendation Engine** for VesselOptima (SIH26006).

While Phases 1–6 generate operationally and commercially feasible candidates, Phase 7 finds the globally optimal deterministic fleet allocation via HiGHS MILP, Phase 8 conducts discrete scenario stress-testing, and Phase 9 quantifies stochastic uncertainty and tail distributions, Phase 10 answers the ultimate operational question:

> **"Given the optimal allocation, scenario analysis, and quantified uncertainty, what should the fleet decision-maker actually do, and why?"**

```text
Phases 1–6 (Candidate Generation & Feasibility)
       ↓
Phase 7 (HiGHS MILP Optimization Engine) — Sole Source of Truth for Allocation
       ↓
Phase 8 (Scenario Analysis & Sensitivity Engine) — Deterministic Stress Tests
       ↓
Phase 9 (Risk Intelligence & Uncertainty Engine) — Stochastic Copulas & VaR/CVaR
       ↓
PHASE 10 (DECISION INTELLIGENCE & EXPLAINABLE RECOMMENDATIONS)
       ↓
Phases 11–13 (Audit, Workflow, and Production Verification)
```

### Strict Architectural Principles
1. **Phase 10 is NOT an Optimizer**: No second MILP, no greedy heuristics, no alternate allocation engines. Phase 7 remains the sole allocator.
2. **Transparent Determinism**: Zero opaque black-box machine learning or LLMs. Every recommendation, reason code, score, and explanation is rule-based and derived deterministically from stored authoritative evidence.
3. **Explicit Gating Hurdle Rates**: Thresholds for `PROCEED`, `PROCEED_WITH_CAUTION`, `RECONSIDER`, and `REJECT` are versioned, documented, and fully auditable.
4. **Air-Gap Compliance**: 100% offline, local computation with zero external socket or cloud dependencies.
5. **Strict USD Denomination**: All financial figures are explicitly denominated in USD ($).

---

## 2. Core Decision Formulations

### 2.1 Composite Decision Score Formulation ($[0, 100]$)

The Decision Score synthesizes five core operational dimensions into a normalized 0–100 benchmark:

$$\text{Decision Score} = w_e \cdot \text{EconSub} + w_{rel} \cdot \text{RelSub} + w_{rob} \cdot \text{RobSub} - w_{risk} \cdot \text{RiskPen} - w_{sched} \cdot \text{SchedPen}$$

Default weights:
* **Economic Performance** ($w_e = 0.35$): Proportional to benchmark contribution hurdle.
* **Plan Reliability** ($w_{rel} = 0.25$): Institutional reliability score $[0, 100]$ from Phase 9.
* **Scenario Robustness** ($w_{rob} = 0.20$): Scenario survival rate $[0, 1.0] \times 100$ under stress testing.
* **Tail Risk Penalty** ($w_{risk} = 0.10$): Deductions for loss probability ($> 5\%$) and downside CVaR95 ratio ($> 20\%$).
* **Schedule Fragility Penalty** ($w_{sched} = 0.10$): Deductions for laycan miss probability ($> 5\%$) and tight buffer ($< 2.0$ days).

### 2.2 Risk-Adjusted Economic Contribution

$$\text{Risk-Adjusted Contribution} = E[\Pi] - \lambda \cdot \text{CVaR}_{95,\text{downside}}$$

* Where $\lambda = 0.50$ (configurable risk-aversion parameter).
* Explicitly identified as a **DECISION RISK-ADJUSTED METRIC**, distinguished from the Phase 7 **OPTIMIZATION OBJECTIVE**.

### 2.3 Confidence Assessment Tiers
* **HIGH**: Complete Phase 7 MILP, Phase 8 scenarios, Phase 9 simulation ($N \ge 1,000$), decision stability $\ge 0.80$, zero data gaps.
* **MEDIUM**: Complete optimization and risk simulation, but stability between $0.50$ and $0.80$ or missing scenarios.
* **LOW**: Missing risk simulation, stability $< 0.50$, or critical data gaps.

---

## 3. Recommendation Gating Rules

| Recommendation Type | Gating Conditions | Typical Primary Reason Codes | Action Advice |
| :--- | :--- | :--- | :--- |
| **PROCEED** | Score $\ge 75$, Loss Prob $\le 5\%$, CVaR ratio $\le 20\%$, Buffer $\ge 2.0\text{d}$, Laycan Miss $\le 5\%$ | `RC_SUPERIOR_ECONOMICS`<br>`RC_ROBUST_UNDER_STRESS`<br>`RC_NEGLIGIBLE_TAIL_RISK` | Execute deployment as scheduled; maintain standard voyage tracking. |
| **PROCEED_WITH_CAUTION** | Score $\ge 50$, Strategy-flip identified OR CVaR ratio $> 20\%$ OR Laycan Miss $> 5\%$ | `RC_STRATEGY_FLIP_WARNING`<br>`RC_TAIL_LOSS_EXPOSURE`<br>`RC_LAYCAN_MISS_RISK` | Execute subject to bunker hedging and active laycan buffer management. |
| **RECONSIDER** | Score $< 50$ OR Loss Prob $> 15\%$ OR Reliability $< 60\%$ | `RC_HIGH_LOSS_PROBABILITY`<br>`RC_INSUFFICIENT_ECONOMIC_RETURN` | Suspend execution; review alternative allocation candidates or reschedule. |
| **REJECT** | Expected Contribution $\le 0$ OR Loss Prob $\ge 35\%$ | `RC_NEGATIVE_EXPECTED_CONTRIBUTION`<br>`RC_EXTREME_TAIL_RISK` | Do not execute; commercially or operationally non-viable. |

---

## 4. Strategy-Flip Decision Resolution

In maritime chartering, a high-yield plan often carries acute downside tail risk. Phase 10 directly resolves the canonical strategy-flip trade-off:

* **Plan A**: Expected Return = \$730,000; 95% CVaR tail loss = \$295,000; Loss Probability = 9.5%.
  * $\text{Risk-Adjusted Contribution} = \$730,000 - 0.50 \times \$295,000 = \$582,500$.
  * Phase 10 Classification: **`PROCEED_WITH_CAUTION`** (`RC_STRATEGY_FLIP_WARNING`).
* **Plan B**: Expected Return = \$685,000; 95% CVaR tail loss = \$15,000; Loss Probability = 0.5%.
  * $\text{Risk-Adjusted Contribution} = \$685,000 - 0.50 \times \$15,000 = \$677,500$.
  * Phase 10 Classification: **`PROCEED`** (`RC_ROBUST_UNDER_STRESS`).

**Decision Verdict**: Plan B dominates Plan A by **+$95,000$ in Risk-Adjusted Economic Return** and preserves operational resilience against fuel price spikes.
