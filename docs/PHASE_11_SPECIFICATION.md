# VesselOptima — Phase 11 Specification: Decision Governance, Audit & Institutional Control Layer

## Tamper-Evident SHA-256 Audit Chains, Separation of Duties & Decision Immutability

---

## 1. Executive Summary & Architectural Scope

Phase 11 delivers the **Decision Governance, Audit & Institutional Control Layer** for VesselOptima (SIH26006).

While Phase 7 solves the global fleet allocation via HiGHS MILP, Phase 8 evaluates scenario robustness, Phase 9 quantifies stochastic tail risk, and Phase 10 produces explainable decision synthesis, Phase 11 answers the institutional enterprise governance question:

> **"How do we prove beyond doubt what decisions were made, why, by whom, under what exact policy, and verify that the decision records have never been tampered with or modified in place?"**

```text
Phases 1–6 (Candidate Generation & Feasibility)
       ↓
Phase 7 (HiGHS MILP Optimization Engine) — Sole Source of Truth for Allocation
       ↓
Phase 8 (Scenario Analysis & Sensitivity Engine) — Deterministic Stress Tests
       ↓
Phase 9 (Risk Intelligence & Uncertainty Engine) — Stochastic Copulas & VaR/CVaR
       ↓
Phase 10 (Decision Intelligence & Explainable Recommendations) — Actionable Verdicts
       ↓
PHASE 11 (DECISION GOVERNANCE, AUDIT & INSTITUTIONAL CONTROL LAYER)
       ↓
Phases 12–13 (Reporting, Verification & Deployment)
```

### Strict Architectural Boundaries
1. **Phase 11 is NOT an Optimizer**: Phase 11 does not alter Phase 7 allocations or introduce secondary optimization heuristics.
2. **No Black-Box Machine Learning or LLMs**: All policy evaluations, hash calculations, and workflow state transitions are 100% deterministic, rule-based, and auditable.
3. **Cryptographic Immutability**: All decision packages are sealed with SHA-256 canonical JSON digests. Once approved, packages cannot be edited in place.
4. **Append-Only, Hash-Chained Audit Trails**: Every state change produces an audit event linked to its predecessor via `previous_hash`, where Genesis has `previous_hash = "GENESIS"`.
5. **Strict Separation of Duties**: The creator of a decision package is strictly forbidden from approving it (`creator != approver`). Approvals require `APPROVER` or `ADMIN` roles.
6. **Air-Gap Compliance**: 100% offline, local computation with zero external network or socket dependencies.
7. **Strict USD Denomination**: All financial metrics remain strictly USD-denominated ($).

---

## 2. Core Governance Components

### 2.1 Decision Package Structure & Canonical Hashing
A Decision Package is an immutable container encapsulating:
* **Upstream Evidence Lineage**: Linkages to Phase 7 (`optimization_run_id`), Phase 8 (`scenario_run_id`), Phase 9 (`risk_run_id`), and Phase 10 (`decision_run_id`).
* **Analytical Metrics Snapshot**: Decision score, confidence tier, expected contribution ($), risk-adjusted contribution ($), loss probability, 95% CVaR tail loss ($), and plan reliability score.
* **Deterministic Hashes**: `input_hash`, `output_hash`, and sealed `package_hash`.
* **Canonical JSON Digest**: Serialization enforces strict alphabetical key sorting, compact non-whitespace delimiters, and uniform float rounding so the hash is mathematically invariant across platforms.

### 2.2 Lifecycle State Machine
```text
[DRAFT]
   │
   ▼ validate_package_evidence()
[VALIDATED]
   │
   ▼ submit_package()
[SUBMITTED]
   │
   ├── review_package() ──► [UNDER_REVIEW]
   │                              │
   │                              ├── approve_package() ──► [APPROVED] (Sealed / Immutable)
   │                              └── reject_package()  ──► [REJECTED]
   └── approve_package() ──► [APPROVED]
```
* **Validation Gating**: Submissions require complete evidence (MILP allocation, stochastic risk metrics, decision run ID, and policy configuration).
* **Immutability Enforcement**: Once a package reaches `APPROVED`, modifying it raises `PACKAGE_ALREADY_FINALIZED`. Revisions require creating a child version ($V1 \to V2$).

### 2.3 Cryptographic Hash-Chained Audit Trail
Audit events follow blockchain-grade sequential linking:
$$\text{Event}_1: \text{previous\_hash} = \text{"GENESIS"}, \quad \text{event\_hash} = \text{SHA-256}(\text{Event}_1)$$
$$\text{Event}_N: \text{previous\_hash} = \text{Event}_{N-1}.\text{event\_hash}, \quad \text{event\_hash} = \text{SHA-256}(\text{Event}_N)$$
Verification checks:
1. Strict sequence continuity ($1, 2, 3, \dots, N$).
2. Genesis parent pointer validation.
3. Sequential parent hash continuity.
4. Content recalculation check (detects in-place payload alteration, deletion, or reordering).

### 2.4 Separation of Duties & Role Access Control
| Institutional Role | Can Create Package | Can Validate Evidence | Can Submit for Review | Can Review | Can Approve | Can Override | Can Change Policy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ANALYST** | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| **REVIEWER** | ✗ | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ |
| **APPROVER** | ✗ | ✓ | ✗ | ✓ | ✓* | ✓* | ✗ |
| **ADMIN** | ✓ | ✓ | ✓ | ✓ | ✓* | ✓* | ✓ |
| **AUDITOR** | ✗ | ✗ (Read only) | ✗ | ✗ | ✗ | ✗ | ✗ |

*\*Subject to separation of duties: `actor != creator`. Self-approval results in immediate `403 Forbidden` (`SELF_APPROVAL_FORBIDDEN`).*

### 2.5 Human Override Governance
When commercial commitments mandate departing from the analytical model:
* **The model recommendation is NEVER overwritten or erased.** Both the model verdict and the overridden human decision are preserved side-by-side.
* Requires mandatory business justification (minimum 5 characters).
* Requires formal risk acknowledgement of Phase 9 downside tail loss.
* Logs approver attribution and signs with audit event `OVERRIDE_RECORDED`.

### 2.6 Decision Reproducibility Verification
Allows enterprise compliance officers to re-evaluate the decision pipeline from stored upstream references:
* Computes real-time decision scores and recommendations from recorded run IDs.
* Compares outputs bit-for-bit with stored package metrics.
* Reports `REPRODUCIBLE` or highlights granular field-by-field discrepancies.

---

## 3. Database Schema

Seven new relational models in `backend/app/models/domain.py` managed under Alembic migration `11f2a3b4c5d6`:
1. `decision_packages`: Core immutable package metadata, status, metrics snapshot, and hashes.
2. `decision_package_versions`: Lineage version history ($V1 \to V2$) with change summaries.
3. `governance_audit_events`: Append-only, hash-chained ledger events.
4. `approval_actions`: Formal review, approval, and rejection workflow actions.
5. `decision_overrides`: Human operational overrides with rationale and attribution.
6. `decision_configurations`: Versioned decision policies and hurdle weights.
7. `configuration_changes`: Audited field-level diffs between configuration versions.
