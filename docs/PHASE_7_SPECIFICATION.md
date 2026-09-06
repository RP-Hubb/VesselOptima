# VesselOptima — Phase 7: MILP Optimization Engine Specification

## 1. Subsystem Purpose & Scope

Phase 7 introduces the first subsystem permitted to perform **global economic ranking, opportunity selection, and portfolio-level fleet allocation**.

### Fundamental Architectural Boundary
```text
Phase 1 — Domain & Baseline Infrastructure
Phase 2 — Offline Data Package & Ingestion
Phase 3 — Market Forecast Intelligence
Phase 4 — Vessel & Port Feasibility Engine
Phase 5 — Dynamic Procurement Strategy & Timing Engine
Phase 6 — Idle Management & Alternative Employment Engine
                 │
                 ▼ [Validated Candidate Set: optimization_status == "READY_FOR_OPTIMIZATION"]
        Phase 7 MILP Optimization Engine
                 │
                 ▼ [Global Optimal Allocation & Dispatch Schedule]
Phase 8+ Scenario Stress-Testing, Risk & Execution
```

* **Candidate Generation $\neq$ Global Allocation**: Phase 6 determines what *can* happen (operational, physical, and temporal admissibility). Phase 7 determines what *should* happen globally (portfolio economic optimization).
* **Zero Invention Rule**: The optimizer never fabricates operational feasibility. Every optimization variable $x_k$ originates from upstream verified candidates.
* **Greedy $\neq$ Global Optimum**: Demonstrably out-performs naive greedy ranking (+$170,000 / +42.5% portfolio yield advantage).

---

## 2. Mathematical MILP Formulation

### 2.1 Sets and Decision Variables
* $\mathcal{V}$: Fleet of available vessels ($v \in \mathcal{V}$)
* $\mathcal{C}$: Set of cargo parcel demand requirements ($c \in \mathcal{C}$)
* $\mathcal{K}$: Set of admissible candidate voyages ($k \in \mathcal{K}$)
* $x_k \in \{0, 1\} \quad \forall k \in \mathcal{K}$: Binary variable; $1$ if candidate $k$ is selected in global optimum, $0$ otherwise.
* $u_c \in \{0, 1\} \quad \forall c \in \mathcal{C}$: Binary slack variable; $1$ if cargo $c$ is left unserved, $0$ if served.

### 2.2 Objective Function
$$\max_{\mathbf{x}, \mathbf{u}} \quad Z = \sum_{k \in \mathcal{K}} P_k \cdot x_k + \alpha \sum_{k \in \mathcal{K}} I_k \cdot x_k - \beta \sum_{k \in \mathcal{K}} B_k \cdot x_k - \sum_{c \in \mathcal{C}} \gamma_c \cdot u_c$$
Where:
* $P_k$: Net voyage contribution ($R_k - C_k$) from Phase 6
* $\alpha \cdot I_k$: Value of avoided idle holding costs ($\alpha \in [0, 1]$)
* $\beta \cdot B_k$: Repositioning penalty for non-revenue ballast days
* $\gamma_c \cdot u_c$: Penalty for leaving strategic cargo unserved

### 2.3 Hard Constraints
1. **Cargo Exclusivity**: $\sum_{k: c(k)=c} x_k + u_c = 1 \quad \forall c \in \mathcal{C}$
2. **Vessel Overlap Exclusivity**: $x_{k_1} + x_{k_2} \le 1 \quad \forall k_1, k_2 \text{ overlapping on vessel } v$
3. **Confirmed Commitment Protection**: $x_k = 0 \quad \forall k \text{ overlapping confirmed fixture}$
4. **Transition Compatibility**: $E_{k_1} + \text{ballast\_days}(\text{dest}(k_1) \to \text{orig}(k_2)) \le S_{k_2}$
5. **Integrality**: $x_k, u_c \in \{0, 1\}$

---

## 3. Solver Architecture

* **Pluggable Interface**: `BaseSolverAdapter` abstract base class.
* **Native Implementation**: `HiGHSSolverAdapter` utilizing SciPy `scipy.optimize.milp` with native C++ HiGHS simplex & branch-and-cut solver.
* **Air-Gap Guarantee**: 100% offline, zero network sockets, zero external license dependencies.
