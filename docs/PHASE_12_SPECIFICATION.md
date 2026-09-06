# VesselOptima — Phase 12 Specification: Maritime Data Integration & Data Quality Governance

## Air-Gapped Maritime Data Foundation, 4-Tier Validation, 6-Factor Quality Scoring & Stale Decision Detection

---

## 1. Executive Summary & Architectural Scope

Phase 12 establishes the **Maritime Data Integration & Data Quality Governance Layer** for VesselOptima (SIH26006).

While Phase 7 solves the global fleet allocation via HiGHS MILP, Phase 8 evaluates deterministic scenarios, Phase 9 quantifies stochastic tail risk, Phase 10 synthesizes explainable recommendations, and Phase 11 governs decisions with tamper-evident audit chains, Phase 12 answers the foundational institutional question:

> **"How do we guarantee that all operational, market, and fleet inputs ingested into VesselOptima are rigorously validated, normalized, quality-scored, cryptographically sealed, and that upstream data revisions automatically flag dependent downstream decisions without mutating historical audit records?"**

```text
==================================================================================================
PHASE 12 (MARITIME DATA INTEGRATION & DATA QUALITY GOVERNANCE LAYER)
Air-Gapped Ingestion • 4-Tier Validation • 6-Factor Quality Scoring • Version Diff • Stale Flagging
==================================================================================================
       ↓
Phases 1–6 (Candidate Generation & Physical Feasibility)
       ↓
Phase 7 (HiGHS MILP Optimization Engine) — Sole Source of Truth for Fleet Allocation
       ↓
Phase 8 (Scenario Analysis & Sensitivity Engine) — Deterministic Stress Testing
       ↓
Phase 9 (Risk Intelligence & Uncertainty Engine) — Stochastic Copulas & Tail VaR/CVaR
       ↓
Phase 10 (Decision Intelligence & Explainable Recommendations) — Actionable Verdicts
       ↓
Phase 11 (Decision Governance & Institutional Control) — Immutable Audit Packages
```

### Strict Architectural Boundaries
1. **Phase 12 is NOT an Optimizer**: Phase 12 is strictly a data ingestion, normalization, validation, quality scoring, versioning, and impact analysis layer. It does not replace or alter Phase 7 (MILP) or any downstream engines.
2. **No Black-Box Machine Learning or LLMs**: All validation rules, quality metrics, quarantine triggers, and diff comparisons are 100% deterministic, rule-based, and auditable.
3. **100% Air-Gap Compliance**: Zero external network or socket connections. Local file ingestion (CSV/JSON) only. Future live API adapters are non-active stubs (`FutureLiveApiAdapter` raises an air-gap violation error).
4. **Currency Transparency**: Preserves original currency metadata (e.g. INR, EUR, USD) without implicit FX conversion. Downstream optimization engines remain strictly USD-denominated ($).
5. **Decision Immutability & Stale Decision Flagging**: When a dataset is superseded ($V1 \to V2$), historical Phase 11 Decision Packages are **never mutated**; instead, downstream impact analysis flags dependent packages as `STALE_INPUT` / `REQUIRES_REVIEW`.
6. **Controlled Data Lifecycle**: `IMPORTED` $\to$ `VALIDATING` $\to$ `VALID` $\to$ `APPROVED` (or `INVALID`, `QUARANTINED`, `REJECTED`, `SUPERSEDED`).

---

## 2. Declarative Dataset Contracts

VesselOptima governs 6 core maritime data domains with declarative schemas:

| Domain | Business Key | Critical Mandatory Fields | Physical Maritime Constraints |
| :--- | :--- | :--- | :--- |
| **`VESSEL_MASTER`** | `vessel_id` | `vessel_id`, `vessel_name`, `dwt`, `loa`, `beam`, `draft`, `service_speed`, `fuel_consumption` | DWT $\ge 100$ MT, LOA $\in [10, 450]$ m, Beam $\in [3, 70]$ m, Draft $\in [1, 30]$ m, Speed $\in [3, 35]$ kts, Fuel $\in [1, 250]$ MT/day |
| **`PORT_REFERENCE`** | `port_id` | `port_id`, `port_name`, `latitude`, `longitude`, `max_draft`, `max_loa` | Latitude $\in [-90, 90]$, Longitude $\in [-180, 180]$, Max Draft $\in [1, 35]$ m, Max LOA $\in [10, 500]$ m |
| **`CARGO_DEMAND`** | `cargo_id` | `cargo_id`, `cargo_name`, `origin_port_id`, `destination_port_id`, `quantity_mt`, `laycan_start`, `laycan_end` | Quantity $> 0$, Origin $\neq$ Destination, Laycan Start $\le$ Laycan End |
| **`VOYAGE_FIXTURE`**| `fixture_id` | `fixture_id`, `route_code`, `rate_usd_per_mt`, `fixture_date` | Rate $\ge 0$ USD/MT |
| **`BUNKER_SERIES`** | `port_id:fuel_type:price_date` | `port_id`, `fuel_type`, `price_usd_per_mt`, `price_date` | Price $> 0$ USD/MT |
| **`OPERATIONAL_EVENT`**| `event_id` | `event_id`, `entity_type`, `entity_id`, `event_type`, `event_timestamp` | Valid event types, non-ambiguous UTC timestamp |

---

## 3. Four-Tier Validation Engine

Each ingested record passes sequentially through 4 deterministic validation tiers:

```text
Raw Record
   │
   ▼
[Tier 1: Structural Validation] ──(Missing required field)──► DATASET_REJECTION / INVALID
   │
   ▼
[Tier 2: Type & Unit Validation] ──(Unparseable type / Ambiguous tz)──► ROW_QUARANTINE
   │
   ▼
[Tier 3: Physical Maritime Bounds] ──(Negative DWT / Speed / Invalid Lat)──► ROW_QUARANTINE
   │
   ▼
[Tier 4: Relational Rules] ──(Origin == Destination / Inverted Laycan)──► ROW_QUARANTINE
   │
   ▼
Valid Records Pool ──► Quality Scoring ──► Cryptographic Hashing ──► VALID Status
```

1. **Tier 1: Structural Validation**: Confirms all mandatory fields are present and non-empty. Violations reject the dataset or quarantine rows (`MISSING_REQUIRED_FIELD`).
2. **Tier 2: Type & Unit Validation**: Numeric parsing with unit stripping (e.g. `"70,000 MT"` $\to 70000.0$), ISO8601 UTC timestamp normalization with strict rejection of ambiguous timezones, and preservation of currency metadata without implicit FX conversion.
3. **Tier 3: Physical Maritime Constraints**: Enforces naval architecture and physical bounds ($DWT > 0$, $Speed > 0$, $Draft > 0$, $Latitude \in [-90, 90]$).
4. **Tier 4: Relational Rules & Cross-Field Constraints**: Enforces business logic (e.g., $Origin \neq Destination$, $LaycanStart \le LaycanEnd$, and duplicate business-key prevention).

---

## 4. Transparent 6-Factor Quality Scoring

Datasets receive an objective quality score ($0.0 - 100.0\%$) evaluated deterministically with documented institutional weights:

$$\text{Quality Score} = 0.25 \cdot Q_{\text{comp}} + 0.25 \cdot Q_{\text{valid}} + 0.20 \cdot Q_{\text{cons}} + 0.10 \cdot Q_{\text{uniq}} + 0.10 \cdot Q_{\text{time}} + 0.10 \cdot Q_{\text{prov}}$$

* **Completeness (25%)**: Ratio of non-null fields populated across all schema columns.
* **Validity (25%)**: Percentage of records passing 100% of validation rules.
* **Consistency (20%)**: Field-type compliance and relational integrity score.
* **Uniqueness (10%)**: Deduplication ratio ($100\% - \text{Duplicate Rate}$).
* **Timeliness (10%)**: Temporal decay against domain freshness horizons (`CURRENT` = 100%, `AGING` = 50%, `STALE` = 0%).
* **Provenance (10%)**: Lineage completeness (source origin, original filename, SHA-256 hash, and actor attribution).

---

## 5. Versioning, Cryptographic Hashing & Downstream Impact Analysis

### 5.1 Canonical Content Hashing
Datasets and individual records are hashed using SHA-256 with canonical JSON serialization (alphabetically sorted keys, compact separators `","` and `":"`, float precision canonicalization).
$$\text{Content Hash} = \text{SHA-256}(\text{CanonicalJSON}(\text{NormalizedRecords}, \text{Metadata}))$$

### 5.2 Granular Record Diff Engine ($V1 \to V2$)
When a new dataset version is uploaded, the differential engine computes row-level diffs:
* `ADDED`: New business keys present in target but absent in base.
* `REMOVED`: Business keys present in base but absent in target.
* `MODIFIED`: Existing business keys with field-level value deltas (`old` $\to$ `new`).
* `UNCHANGED`: Existing business keys with identical cryptographic record hashes.

### 5.3 Stale Decision Detection
When a dataset version is updated:
1. Historical approved Phase 11 Decision Packages are **never altered or deleted** (preserving institutional immutability).
2. Dependent packages are flagged as `STALE_INPUT` with impact severity (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
3. An audit notice is issued recommending re-running upstream optimizers (Phase 7) and risk simulations (Phase 9) for subsequent decision packages.
