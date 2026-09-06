# VesselOptima — Phase 12 Implementation: Maritime Data Integration & Data Quality Governance

## Technical Implementation, Verification Baseline & Architecture

---

## 1. Overview & Verification Baseline

Phase 12 delivers the controlled data foundation for VesselOptima (SIH26006). All automated verification suites and production builds pass cleanly:

* **Phase 12 Tests**: 25/25 PASS (`backend/tests/test_data_governance.py`)
* **Full Regression**: 232/232 PASS (`backend/tests/ -q` covering Phases 1–12)
* **Frontend Production Build**: PASS (`npm run build` with 16/16 routes compiled)
* **Alembic Head Revision**: `12a3b4c5d6e7`
* **Air-Gap Compliance**: PASS (Zero outbound network socket calls; `FutureLiveApiAdapter` disabled)
* **USD-Only Economics**: Preserved (Non-USD metadata preserved without implicit FX conversions)

---

## 2. Directory Structure & File Manifest

```text
backend/
├── alembic/versions/
│   └── 12a3b4c5d6e7_add_data_governance_tables.py   # Alembic DDL migration (9 tables)
├── app/
│   ├── api/v1/
│   │   └── data.py                                   # REST API endpoints for Phase 12
│   ├── engines/data/
│   │   ├── __init__.py                               # Public exports
│   │   ├── adapters/
│   │   │   ├── base.py                               # DataSourceAdapter interface & FutureLiveApiAdapter stub
│   │   │   └── local_file.py                         # LocalFileAdapter for air-gapped CSV/JSON
│   │   ├── contracts.py                              # Declarative contracts for 6 maritime domains
│   │   ├── hashing.py                                # Canonical JSON serialization & SHA-256 digests
│   │   ├── impact.py                                 # Downstream dependency & stale decision analyzer
│   │   ├── models.py                                 # ValidationResult, QualityScoreResult, RecordDiff dataclasses
│   │   ├── normalization.py                          # Unit stripping, UTC timestamp parser, currency preservation
│   │   ├── quality.py                                # 6-factor quality scoring & freshness horizons
│   │   ├── quarantine.py                             # Quarantine ledger builder & defect reason codes
│   │   ├── reason_codes.py                           # Enums for statuses, layers, severities, defect codes
│   │   ├── service.py                                # DataGovernanceService orchestrator & canonical demo seeder
│   │   ├── validation.py                             # 4-tier validation pipeline
│   │   └── versioning.py                             # Granular record diff engine (ADDED, REMOVED, MODIFIED, UNCHANGED)
│   ├── models/
│   │   ├── __init__.py                               # Re-exports of all 9 models
│   │   └── domain.py                                 # SQLAlchemy ORM models (GovernanceDataset, DatasetVersion, etc.)
│   └── schemas/
│       └── data.py                                   # Pydantic request/response schemas
└── tests/
    └── test_data_governance.py                       # 25 automated unit and integration tests

frontend/
├── src/
│   ├── app/data/page.tsx                             # Institutional Dark Terminal Data Governance Console
│   ├── lib/api.ts                                    # Centralized API client functions
│   └── types/api.ts                                  # TypeScript interfaces & types
```

---

## 3. Database Architecture (Alembic Head: `12a3b4c5d6e7`)

Phase 12 introduces 9 relational tables:

1. `governance_datasets`: Master catalog with `dataset_id`, `dataset_type`, `current_version`, `status`, `content_hash`, `quality_score`, `freshness_status`, `created_by`, `approved_by`.
2. `dataset_versions`: Version history with parent version links, schema versions, and content hashes.
3. `dataset_records`: Ingested records with individual row-level SHA-256 hashes (`record_hash`) and extracted `business_key`.
4. `dataset_validations`: 4-tier validation outcomes per layer (`STRUCTURAL`, `TYPE`, `PHYSICAL`, `RELATIONAL`) with defect metrics.
5. `dataset_qualities`: 6-factor quality breakdowns (`completeness`, `validity`, `consistency`, `uniqueness`, `timeliness`, `provenance`) and evaluated freshness.
6. `dataset_provenances`: Ingestion lineage, source name, original filename, original file SHA-256 hash, import actor, and transformation chain.
7. `quarantine_records`: Defect quarantine records with row index, failing field, error code, original value, and severity (`ROW_QUARANTINE`, `DATASET_REJECTION`).
8. `dataset_changes`: Record-level diffs between versions (`ADDED`, `REMOVED`, `MODIFIED`, `UNCHANGED`) with before/after field changes.
9. `dataset_impacts`: Downstream analytical impact assessments across Phases 4–11 and stale Phase 11 decision package IDs.

---

## 4. REST API Reference (`/v1/data`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/data/import` | Ingest and validate a new dataset (CSV/JSON). |
| `GET` | `/v1/data/datasets` | List governance datasets with optional type filter. |
| `GET` | `/v1/data/datasets/{id}` | Retrieve dataset details, quality report, and validation layers. |
| `POST` | `/v1/data/datasets/{id}/version` | Ingest a new child version ($V1 \to V2$), triggering diff and impact analysis. |
| `POST` | `/v1/data/datasets/{id}/approve` | Formally approve a valid dataset (`creator != approver`). |
| `POST` | `/v1/data/datasets/{id}/reject` | Reject a dataset with mandatory defect rationale. |
| `GET` | `/v1/data/datasets/{id}/quarantine` | Retrieve quarantine defect records for a dataset. |
| `GET` | `/v1/data/datasets/{id}/diff` | Retrieve version diff between baseline and target versions. |
| `GET` | `/v1/data/datasets/{id}/impact` | Retrieve downstream analytical impact and flagged stale decisions. |
| `GET` | `/v1/data/demo/seed` | Seed canonical demonstration datasets ($V1$ and $V2$). |

---

## 5. Automated Test Suite (25 Tests)

```text
tests/test_data_governance.py:
  test_valid_vessel_master_import                     PASSED
  test_invalid_physical_value_negative_dwt           PASSED
  test_missing_required_field                        PASSED
  test_unit_normalization                            PASSED
  test_timestamp_normalization_utc                   PASSED
  test_ambiguous_timestamp_fails                     PASSED
  test_currency_explicitness                         PASSED
  test_duplicate_business_key_detection              PASSED
  test_relational_origin_destination_check           PASSED
  test_deterministic_quality_score                   PASSED
  test_freshness_classification                      PASSED
  test_hash_determinism                              PASSED
  test_tamper_detection                              PASSED
  test_dataset_versioning                            PASSED
  test_dataset_diff_engine                           PASSED
  test_quarantine_retention                          PASSED
  test_dataset_approval_workflow                     PASSED
  test_downstream_impact_analysis                    PASSED
  test_stale_decision_detection                      PASSED
  test_audit_event_logging                           PASSED
  test_data_api_lifecycle                            PASSED
  test_sqlite_persistence                           PASSED
  test_quarantine_api_endpoint                       PASSED
  test_air_gap_compliance                           PASSED
  test_canonical_demo_data_seeding                   PASSED
```
