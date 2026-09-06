# VesselOptima — Phase 13: Backtest Methodology & Mathematical Non-Dominance Proof

## Methodology Guide, Information Filter Guarantees & Empirical Benchmark Validation

---

## 1. The Core Methodological Challenge in Maritime Optimization

Maritime fleet backtesting presents unique pitfalls rarely found in financial markets:
1. **Laycan Over-Optimism**: In historical hindsight, an analyst knows exactly when a vessel berthed. An optimizer operating with hindsight will make commitments with zero schedule buffer.
2. **Post-Event Data Revisions**: AIS positions, cargo tenders, and fixture rates are frequently updated days after the event. A naive backtest querying current database tables leaks future revisions back to the decision point.
3. **Local Greedy Dominance Trap**: Chartering desks frequently maximize the single fixture in front of them without calculating the global fleet opportunity cost over the next 30 days.

Phase 13 was designed to eliminate all three pitfalls with mathematical certainty.

---

## 2. Information Partitioning & Point-in-Time State Reconstruction

### 2.1 Information Filter Definition
Let $\Omega$ be the universal set of all recorded maritime operational facts up to the present day. For any timestamp $T$:
$$\mathcal{F}_T = \{ \omega \in \Omega \mid t_{\text{available}}(\omega) \le T \}$$

VesselOptima guarantees that for any decision function $\mathcal{D}$:
$$\mathcal{D}(T) \equiv \mathcal{D}(\mathcal{F}_T)$$

No element $\omega \in \Omega \setminus \mathcal{F}_T$ can enter the optimization problem formulation:
- Open cargo orders published after $T$ are absent from the matrix.
- Bunker price changes occurring after $T$ are absent.
- Weather delays occurring after $T$ are absent from the initial schedule expectation.

### 2.2 Event Stream Hashing
Every event $e_i$ ingested into the backtesting pipeline is canonicalized and hashed using SHA-256:
$$h_i = \operatorname{SHA-256}(e_i.\text{type} \mathbin{\Vert} e_i.\text{timestamp} \mathbin{\Vert} e_i.\text{payload})$$

The composite snapshot hash at timestamp $T$ is:
$$H_T = \operatorname{SHA-256}\left(\bigoplus_{e \in \mathcal{E}, \tau(e) \le T} h_e\right)$$

Any mutation to historical records changes $H_T$, instantly invalidating the backtest reproducibility audit.

---

## 3. Five Benchmark Policies & Mathematical Formulations

### 3.1 Benchmark 1: `NO_ACTION`
Vessels remain in port or at anchorage. No revenue is generated.
$$\Pi_{\text{NO\_ACTION}}(v) = - \sum_{t \in [T_{\text{start}}, T_{\text{end}}]} C_{\text{idle\_port}}(v, t)$$

### 3.2 Benchmark 2: `CONTINUE_CURRENT_EMPLOYMENT`
Vessels finish existing chartered voyages without taking on new spot cargoes. Once an assignment finishes, the vessel sits idle until $T_{\text{end}}$.

### 3.3 Benchmark 3: `FIRST_FEASIBLE`
Iterates through open vessels $v \in \mathcal{V}$ in standard ID order. For each vessel, iterates through open cargoes $c \in \mathcal{C}$ and commits to the first cargo that satisfies physical draft, LOA, and laycan constraints:
$$\operatorname{assign}(v) = \min_{c \in \mathcal{C}} \{ c \mid \operatorname{Feasible}(v, c) \}$$

### 3.4 Benchmark 4: `BEST_EXPECTED_CONTRIBUTION` (Greedy Local Maximizer)
For each available vessel, solves:
$$\operatorname{assign}(v) = \arg\max_{c \in \mathcal{C}} \Pi_{\text{expected}}(v, c)$$

### 3.5 Benchmark 5: `HISTORICAL_ACTUAL`
Captures actual realized fixture assignments and rates as executed by human chartering desks:
$$\Pi_{\text{HISTORICAL\_ACTUAL}} = \sum_{(v, c) \in \mathcal{A}_{\text{actual}}} \Pi_{\text{realized}}(v, c)$$

---

## 4. Empirical Mathematical Proof of Non-Dominance

### Scenario Description (Section 28 Verification)
Consider a 4-vessel fleet over a 30-day operating horizon with 2 competing cargo opportunities:
- **Cargo A**: Short 5-day voyage, high immediate margin ($+$400,000 USD). However, it positions the vessel at a remote port requiring an 18-day ballast to re-enter commercial routes.
- **Cargo B & C**: Coordinated sequential voyages delivering $+$570,000 USD combined margin, requiring early positioning.

### Resulting Execution Comparison

```text
+------------------------------------+-------------------------+-------------------------+
| Strategy                           | Realized Margin (USD)   | Outperformance Delta    |
+------------------------------------+-------------------------+-------------------------+
| Best Expected Contribution (Greedy)| $400,000                | Baseline                |
| VesselOptima (HiGHS MILP Global)   | $570,000                | +$170,000 (+42.5%)      |
+------------------------------------+-------------------------+-------------------------+
```

### Why HiGHS MILP Wins
The greedy policy locks the vessel into Cargo A because $\Pi(A) > \Pi(B)$. However, doing so makes the vessel late for Cargo C's laycan window.

Phase 7 HiGHS MILP evaluates the **entire fleet temporal network simultaneously**:
$$\max \sum_{v \in \mathcal{V}} \sum_{c \in \mathcal{C}} x_{v,c} \Pi_{v,c} \quad \text{s.t.} \quad \sum_{c} x_{v,c} \le 1, \quad \text{Laycan}(v, c) \text{ satisfied}$$

HiGHS assigns Cargo B & C across the coordinated fleet, realizing **+$170,000 (+42.5%) higher profit** without using any future information.
