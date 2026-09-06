# VesselOptima — Phase 7: MILP Optimization Engine Implementation

## 1. Engine Modules (`backend/app/engines/optimization/`)

1. **`reason_codes.py`**:
   - `OptimizationStatus` (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNBOUNDED`, `TIME_LIMIT`, `SOLVER_ERROR`, `EMPTY_MODEL`)
   - `AssignmentSelectionStatus` (`SELECTED`, `MODEL_REJECTED`, `INFEASIBLE_UPSTREAM`, `UNASSIGNED`)
   - `TradeOffReasonCode` (`OPTIMAL_GLOBAL_ALLOCATION`, `CARGO_EXCLUSIVITY_LOST`, `VESSEL_TIMELINE_CONFLICT`, `COMMITMENT_PROTECTED`, `NEGATIVE_ECONOMIC_CONTRIBUTION`, `LOWER_NET_CONTRIBUTION`)

2. **`variables.py`**:
   - `CandidateVariable` ($x_k \in \{0, 1\}$)
   - `CargoSlackVariable` ($u_c \in \{0, 1\}$)
   - `VariableRegistry` indexing and bookkeeping

3. **`constraints.py`**:
   - `ConstraintBuilder` assembling Cargo Exclusivity, Vessel Exclusivity, Commitment Protection, Transition Compatibility, and Custom Linear Constraints.

4. **`objective.py`**:
   - `ObjectiveBuilder` constructing minimization cost vector $c \in \mathbb{R}^N$
   - `ObjectiveDecomposition` producing exact USD audit trail: Gross Revenue, Costs, Net Contribution, Avoided Idle, Ballast Penalty, Unserved Penalty, Global Objective.

5. **`solver.py`**:
   - `BaseSolverAdapter` abstract base class
   - `HiGHSSolverAdapter` wrapping `scipy.optimize.milp` with HiGHS C++ Branch-and-Cut solver.

6. **`model.py`**:
   - `OptimizationModel` coordinating variables, constraints, solver execution, post-solution trade-off diagnostics, and result assembly.

7. **`result.py`**:
   - `OptimizationResult`, `AssignmentResult`, `UnassignedCargoResult`.

8. **`service.py`**:
   - `OptimizationService` orchestrating end-to-end solve, scenario management, candidate ingestion from Phase 6, and transactional database persistence.

---

## 2. Database Migration (`7b8c9d0e1f2a_add_optimization_tables.py`)

* Updated `optimization_runs`: added `run_id`, `total_revenue`, `total_cost`, `total_contribution`, `avoided_idle_cost`, `solver_name`, `solver_status`, `objective_decomposition`, `solver_metadata`, `audit_trail`.
* Created `optimization_assignments`: foreign-keyed to `optimization_runs`, `vessel_profiles`, `cargo_parcels`.

---

## 3. Test Suite & Verification Results

* Test file: `backend/tests/test_optimization_engine.py` (18 tests)
* **Phase 7 tests**: 18 / 18 PASS (100%) in 3.26s
* **Full regression suite**: 121 / 121 PASS (100%) in 29.63s
* **Greedy vs Global Proof**: Confirmed $+\$170,000$ (+42.5%) portfolio advantage over naive greedy ranking.
* **Air-gap isolation**: 0 outbound network requests verified via socket mock trap.
* **Frontend build**: Next.js production build compiled cleanly with code 0 across all 11 routes.
