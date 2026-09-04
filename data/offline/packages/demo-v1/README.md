# VesselOptima — Offline Demonstration Data Package (`demo-v1`)

> [!IMPORTANT]
> **DISCLAIMER & DATA TRUTHFULNESS NOTICE**  
> **DATASET TYPE:** SYNTHETIC DEMONSTRATION DATA  
> **PURPOSE:** Offline SIH 2026 software demonstration, deterministic validation, and offline judging.  
> **NOT FOR:** Real-world chartering, maritime operations, freight trading, or commercial procurement decisions.  
> **This offline package is synthetic demonstration data and must not be interpreted as verified real-world maritime market, vessel, or port data.**

---

## 1. Package Metadata

* **Package ID:** `demo-v1`
* **Package Type:** `OFFLINE_DEMO`
* **Version:** `1.0.0`
* **Schema Version:** `1.0.0`
* **Temporal Coverage:** `2024-01-01` to `2026-08-31` (974 days)
* **Default Provenance Classification:** `SYNTHETIC` (with route freight as `PROXY`)
* **Integrity Mechanism:** SHA-256 hashes per dataset in `manifest.json`

---

## 2. Dataset Inventory

| Directory | Dataset File | Rows | Type | Provenance | Purpose |
|---|---|---|---|---|---|
| `vessel_classes/` | `vessel_classes.csv` | 4 | Dimensional | `SYNTHETIC` | Canonical dry bulk classes (Handysize, Supramax, Panamax, Capesize). |
| `vessels/` | `vessels.csv` | 20 | Registry | `SYNTHETIC` | Synthetic fleet roster with dimensions, speeds, bunker burn, and authority flags. |
| `ports/` | `ports.csv` | 15 | Master Data | `SYNTHETIC` | Key global and Indian dry bulk ports (Paradip, Dhamra, Visakhapatnam, etc.). |
| `ports/` | `port_constraints.csv` | 10 | Rules | `SYNTHETIC` | Draft, LOA, beam, and operational constraints per terminal and berth. |
| `routes/` | `routes.csv` | 12 | Network | `SYNTHETIC` | Normalized origin-to-destination nautical distance pairs. |
| `cargo/` | `cargo_requirements.csv` | 6 | Demand | `SYNTHETIC` | Coking coal, thermal coal, and iron ore parcel shipment demands. |
| `vessel_positions/` | `vessel_positions.csv` | 8 | Operational | `SYNTHETIC` | Vessel availability locations and timestamps. |
| `vessel_positions/` | `vessel_commitments.csv` | 4 | Schedule | `SYNTHETIC` | Immutable schedule commitments bounding idle windows. |
| `market/` | `market_indices.csv` | 4,870 | Time Series | `SYNTHETIC` | Daily Baltic indices (BDI, BCI, BPI, BSI, BHSI) with trend, seasonality, and shocks. |
| `freight/` | `freight_observations.csv` | 4,870 | Time Series | `PROXY` | Route-specific freight rate proxies ($/MT) distinct from broad indices. |
| `bunker/` | `fuel_prices.csv` | 4,870 | Time Series | `SYNTHETIC` | Marine fuel prices (VLSFO, IFO380, MGO) at Singapore, Rotterdam, and Paradip. |
| `congestion/` | `congestion_observations.csv` | 3,896 | Time Series | `SYNTHETIC` | Port waiting times (days) with seasonal monsoon surge patterns. |
| `fx/` | `fx_observations.csv` | 1,948 | Time Series | `SYNTHETIC` | Currency exchange rates (USD/INR, USD/EUR). |
| `contracts/` | `contracts.csv` | 4 | Commercial | `SYNTHETIC` | Master contract archetypes (SPOT, SHORT_TERM, MEDIUM_TERM, MULTI_VOYAGE). |
| `procurement/` | `procurement_windows.csv` | 4 | Planning | `SYNTHETIC` | Procurement lead-time windows and benchmark rates. |
| `idle/` | `idle_windows.csv` | 3 | Decision | `SYNTHETIC` | Detected idle windows for controlled vessels. |
| `employment/` | `employment_candidates.csv` | 3 | Candidates | `DERIVED` | Feasible alternative cargo/voyage employment candidates. |
| `employment/` | `employment_evaluations.csv` | 6 | Evaluation | `DERIVED` | Economic comparison of WAIT, REPOSITION, and ALTERNATIVE_EMPLOYMENT actions. |
| `scenarios/` | `scenarios.csv` | 5 | Stress Tests | `SYNTHETIC` | Stress scenarios (`BASE`, `FUEL_SHOCK_PLUS_20`, `FREIGHT_SPIKE_PLUS_15`, etc.). |

---

## 3. How to Regenerate & Verify

1. **Regenerate Package Data:**
   ```bash
   python scripts/package/generate_offline_package.py
   ```
2. **Generate Manifest with SHA-256 Hashes:**
   ```bash
   python scripts/package/generate_manifest.py
   ```
3. **Verify Manifest Integrity:**
   ```bash
   python scripts/validate/verify_offline_package.py
   ```
4. **Load into Database (OFFLINE_DEMO Mode):**
   ```bash
   python scripts/package/load_offline_package.py
   ```

---

## 4. Referential Integrity Graph

```text
[vessel_classes] ──< [vessels] ──< [vessel_positions]
                           │
                           ├──< [vessel_commitments]
                           │
                           ├──< [idle_windows] ──< [employment_evaluations]
                           │
                           └──< [employment_candidates] >── [cargo_requirements]
                                          │
[ports] ──< [routes] ─────────────────────┘
   │
   └──< [port_constraints]
```

All foreign keys, chronology rules (`window_start < window_end`), and positive physical constraints are validated prior to database persistence.
