# VesselOptima — Phase 9 Specification: Risk Intelligence & Uncertainty Engine

## Institutional Maritime Uncertainty Modeling & Downside Risk Quantification

---

## 1. Executive Summary & Architectural Scope

Phase 9 introduces the **Risk Intelligence & Uncertainty Engine** into VesselOptima (SIH26006).

While Phase 7 solves the deterministic **Mixed-Integer Linear Programming (MILP)** global fleet assignment and Phase 8 conducts **discrete what-if parameter stress testing** (e.g. bunker $+25\%$), Phase 9 models **continuous stochastic uncertainty** across market freight rates, bunker volatility, port congestion delays, and en-route weather delays.

```text
OBSERVE (Phase 2)
   ↓
FORECAST (Phase 3)
   ↓
FEASIBILITY (Phase 4)
   ↓
PROCUREMENT STRATEGY (Phase 5)
   ↓
IDLE / ALTERNATIVE EMPLOYMENT (Phase 6)
   ↓
MILP OPTIMIZATION (Phase 7)
   ↓
SCENARIOS & SENSITIVITY (Phase 8)
   ↓
PHASE 9 — RISK INTELLIGENCE & UNCERTAINTY
   ↓
DECIDE & AUDIT (Phases 10–13)
```

### Strict Architectural Boundaries
1. **Single Source of Truth**: Phase 7 HiGHS MILP remains the sole fleet allocation optimizer.
2. **Analysis, Not Re-optimization**: Phase 9 does NOT silently replace or mutate the Phase 7 objective function. Risk metrics and penalty formulations ($E[\Pi] - \lambda \cdot \text{CVaR}$) serve as an institutional reporting and executive evaluation layer.
3. **Continuous vs Discrete**: Phase 8 evaluates deterministic point perturbations; Phase 9 quantifies stochastic probability distributions ($N = 1,000$ to $100,000$ draws) and joint correlations.
4. **Air-Gap Guarantee**: 100% offline local computation with zero external network or cloud socket dependencies.
5. **Strict Currency Uniformity**: All monetary valuations are strictly denominated in USD ($).

---

## 2. Mathematical Modeling & Probability Framework

### 2.1 Supported Probability Distributions

All risk variables are parameterized with strictly validated domain boundaries:

| Distribution Type | Formulation | Physical Domain Constraints | Typical Maritime Parameter |
| :--- | :--- | :--- | :--- |
| **Lognormal** | $X \sim \text{Lognormal}(\mu, \sigma)$ | $X > 0$ strictly positive | VLSFO / MGO Bunker Price, Weather Delays |
| **Normal** | $X \sim \mathcal{N}(\mu, \sigma^2)$ | Domain checked against truncation | Regional Freight Indices (USD/MT) |
| **Triangular** | $X \sim \text{Triangular}(a, c, b)$ | $a \le c \le b$, $a < b$, $a \ge 0$ for delays | Port Turnaround / Congestion Delays |
| **Uniform** | $X \sim \mathcal{U}(a, b)$ | $a < b$ | Bounded inspection / demurrage windows |
| **Empirical** | Discrete resampled quantiles | $X_i \in \text{Observed}$ | Non-parametric historical residual logs |
| **Deterministic** | $X = c$ | Fixed constant | Contracted fixed charter or bunker price |

### 2.2 Joint Correlation & Gaussian Copula Sampling

Correlated stochastic variables (e.g. bunker prices and freight rates, or loading and discharge port congestion) are sampled jointly using **Gaussian Copulas**:

1. **Correlation Matrix Properties**:
   - Square ($k \times k$), symmetric ($C_{ij} = C_{ji}$), unit diagonal ($C_{ii} = 1.0$), all coefficients in $[-1.0, 1.0]$.
   - Positive semi-definite: $\lambda_{\min}(C) \ge 0$.
2. **Cholesky Factorization**:
   $$C = L L^T$$
   where $L$ is a lower-triangular matrix with positive diagonal elements.
3. **Copula Transformation**:
   - Draw uncorrelated standard normals: $Z \sim \mathcal{N}(0, I_k)$.
   - Correlate: $X_{\text{norm}} = L Z$.
   - Uniform marginals: $U_i = \Phi(X_{\text{norm}, i})$ via standard normal CDF $\Phi$.
   - Target marginals: $S_i = F_i^{-1}(U_i)$ via inverse CDF (Percent Point Function / `ppf`).

---

## 3. Financial & Operational Risk Metrics

### 3.1 Value at Risk (VaR) & Conditional VaR (CVaR)

For a simulated net contribution distribution $\Pi$:
- **$\text{VaR}_{95}$ Level**: The 5th percentile outcome:
  $$P(\Pi \le \text{VaR}_{95}) = 0.05$$
- **$\text{VaR}_{95}$ Downside**: The capital shortfall from expectation:
  $$\text{VaR}_{95,\text{downside}} = E[\Pi] - \text{VaR}_{95}$$
- **$\text{CVaR}_{95}$ (Expected Shortfall)**: The expected contribution in the worst 5% tail:
  $$\text{CVaR}_{95} = E[\Pi \mid \Pi \le \text{VaR}_{95}]$$

### 3.2 Schedule Fragility & Survival Probabilities

For each assignment $j$:
- **Schedule Buffer Days**: $\Delta t_{\text{buffer}} = t_{\text{laycan\_end}} - E[t_{\text{arrival}}]$.
- **Laycan Miss Probability**: Fraction of simulated draws where $t_{\text{arrival}} > t_{\text{laycan\_end}}$.
- **Economic Survival**: $P(\Pi_j > 0)$.
- **Schedule Survival**: $1.0 - P(\text{Laycan Miss})$.
- **Combined Survival**: $P(\Pi_j > 0 \land t_{\text{arrival}} \le t_{\text{laycan\_end}})$.

### 3.3 Plan Reliability Score & Risk Tiers

Composite institutional reliability index $[0, 100]$:
$$\text{Score} = 50\% \cdot \text{Econ Survival} + 30\% \cdot \text{Sched Survival} + 20\% \cdot \text{Tail Factor}$$

| Risk Tier | Loss Probability Threshold | Schedule Miss Threshold | Institutional Action |
| :--- | :--- | :--- | :--- |
| **`LOW`** | $< 5\%$ | $< 5\%$ | Immediate operational release |
| **`MODERATE`** | $5\% - 15\%$ | $5\% - 15\%$ | Standard charter party hedging |
| **`HIGH`** | $15\% - 30\%$ | $15\% - 30\%$ | Additional buffer / bunker adjustment required |
| **`CRITICAL`** | $> 30\%$ | $> 30\%$ | Board / executive review mandatory |

---

## 4. The Critical Risk Flip

A **Critical Risk Flip** occurs when Plan A appears superior under deterministic or expected valuations, but suffers catastrophic tail breakdown compared to Plan B:

$$\begin{aligned}
E[\Pi_A] &> E[\Pi_B] \\
\text{Loss Prob}_A &\gg \text{Loss Prob}_B \\
\text{CVaR}_{95,A} &\ll \text{CVaR}_{95,B}
\end{aligned}$$

Phase 9 detects and articulates this divergence objectively to institutional leadership, empowering informed trade-offs between expected upside and capital preservation.
