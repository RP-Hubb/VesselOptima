"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance Test Suite

Comprehensive automated test verification covering:
1. Valid vessel master import -> VALID
2. Negative DWT -> QUARANTINED (NEGATIVE_PHYSICAL_VALUE)
3. Missing required field -> INVALID (MISSING_REQUIRED_FIELD)
4. Unit normalization (MT, kts) with explicit metadata
5. Timestamp normalization to UTC
6. Ambiguous timestamp failure
7. Currency explicitness (non-USD metadata preserved without implicit FX)
8. Duplicate business-key detection
9. Conflicting duplicate detection
10. Transparent 6-factor quality scoring
11. Freshness classification (CURRENT, AGING, STALE)
12. SHA-256 dataset hash determinism
13. Record-level tamper detection
14. Immutable dataset versioning (V1 -> V2)
15. Dataset diff engine (ADDED, REMOVED, MODIFIED, UNCHANGED)
16. Quarantine ledger retention and defect reason codes
17. Dataset approval workflow
18. Downstream dependency impact analyzer
19. Stale decision package detection (Phase 11 integration)
20. Audit event logging
21. REST API endpoint lifecycle
22. SQLite persistence & transaction integrity
23. Quarantine API endpoint
24. Air-gap offline compliance (zero outbound sockets)
25. Full regression integrity
"""

import json
import socket
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.engines.data import (
    DataGovernanceReasonCode,
    DataGovernanceService,
    DatasetContract,
    DatasetStatus,
    DatasetType,
    FreshnessStatus,
    ImpactLevel,
    LocalFileAdapter,
    QuarantineSeverity,
    RecordChangeType,
    ValidationLayer,
    analyze_dataset_impact,
    calculate_data_quality_score,
    compare_datasets,
    compute_canonical_hash,
    compute_dataset_hash,
    compute_record_hash,
    evaluate_freshness,
    get_contract,
    normalize_record,
    normalize_timestamp_to_utc,
    validate_dataset_records,
    verify_dataset_integrity,
)
from app.engines.governance import GovernanceService
from app.main import app
from app.models.domain import (
    DatasetChange,
    DatasetImpact,
    DatasetProvenance,
    DatasetQuality,
    DatasetRecord,
    DatasetValidation,
    DatasetVersion,
    DecisionPackage,
    GovernanceDataset,
    QuarantineRecord,
)


@pytest.fixture
def db_session(db):
    """Use the test database session from conftest."""
    return db


# ── 1. Valid Vessel Import ────────────────────────────────────────────

def test_valid_vessel_master_import(db_session):
    """Valid vessel records import cleanly into VALID status."""
    service = DataGovernanceService(db_session)
    records = [
        {"vessel_id": "V1", "vessel_name": "Pacific Star", "dwt": 75000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
        {"vessel_id": "V2", "vessel_name": "Atlantic Hero", "dwt": 82000.0, "loa": 229.0, "beam": 32.2, "draft": 14.5, "service_speed": 14.0, "fuel_consumption": 31.0},
    ]
    res = service.import_dataset(
        dataset_type=DatasetType.VESSEL_MASTER,
        name="Test Valid Fleet",
        source_payload=records,
        actor="capt_vance",
    )
    assert res["status"] == "VALID"
    assert res["is_valid"] is True
    assert res["valid_records"] == 2
    assert res["quarantined_records"] == 0
    assert res["quality_score"] > 80.0


# ── 2. Invalid Physical Value (Negative DWT) ──────────────────────────

def test_invalid_physical_value_negative_dwt(db_session):
    """Negative DWT violates physical maritime constraint and triggers ROW_QUARANTINE."""
    service = DataGovernanceService(db_session)
    records = [
        {"vessel_id": "V1", "vessel_name": "Valid Vessel", "dwt": 75000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
        {"vessel_id": "V2", "vessel_name": "Ghost Ship", "dwt": -150000.0, "loa": 229.0, "beam": 32.2, "draft": 14.5, "service_speed": 14.0, "fuel_consumption": 31.0},
    ]
    res = service.import_dataset(
        dataset_type=DatasetType.VESSEL_MASTER,
        name="Test Negative DWT",
        source_payload=records,
        actor="capt_vance",
    )
    assert res["status"] == "QUARANTINED"
    assert res["is_valid"] is False
    assert res["valid_records"] == 1
    assert res["quarantined_records"] == 1

    quarantine = service.get_quarantine_records(res["dataset_id"])
    assert len(quarantine) >= 1
    assert any("dwt" in q["field_name"] for q in quarantine)


# ── 3. Missing Required Field ─────────────────────────────────────────

def test_missing_required_field():
    """Missing required contract field fails structural validation."""
    contract = get_contract(DatasetType.VESSEL_MASTER)
    records = [
        {"vessel_id": "V1", "dwt": 75000.0}  # missing loa, beam, draft, service_speed, fuel_consumption
    ]
    val_res, valid_recs, quar_recs = validate_dataset_records(records, contract)
    assert val_res.is_valid is False
    assert val_res.layer_results["STRUCTURAL"] is False
    missing_fields = [iss.field_name for iss in val_res.issues if iss.error_code == DataGovernanceReasonCode.MISSING_REQUIRED_FIELD]
    assert "vessel_name" in missing_fields
    assert "draft" in missing_fields


# ── 4. Unit Normalization ─────────────────────────────────────────────

def test_unit_normalization():
    """Numeric values with unit strings (70,000 MT, 13.5 kts) normalize cleanly with explicit unit metadata."""
    contract = get_contract(DatasetType.VESSEL_MASTER)
    raw = {
        "vessel_id": "V1",
        "vessel_name": "Star Voyager",
        "dwt": "70,000 MT",
        "loa": "225.0 meters",
        "beam": 32.2,
        "draft": 14.2,
        "service_speed": "13.5 kts",
        "fuel_consumption": "28.5 MT/day",
    }
    normalized, transforms = normalize_record(raw, contract)
    assert normalized["dwt"] == 70000.0
    assert normalized["dwt_unit"] == "MT"
    assert normalized["service_speed"] == 13.5
    assert len(transforms) >= 2


# ── 5. Timestamp Normalization to UTC ──────────────────────────────────

def test_timestamp_normalization_utc():
    """Timezone-aware timestamps normalize correctly to UTC ISO8601."""
    # Tokyo time +09:00
    norm_utc, orig, is_ambig = normalize_timestamp_to_utc("2026-09-06T18:00:00+09:00")
    assert is_ambig is False
    assert norm_utc == "2026-09-06T09:00:00+00:00"

    # IST +05:30
    norm_utc2, _, is_ambig2 = normalize_timestamp_to_utc("2026-09-06T15:30:00+05:30")
    assert is_ambig2 is False
    assert norm_utc2 == "2026-09-06T10:00:00+00:00"


# ── 6. Ambiguous Timestamp Fails ──────────────────────────────────────

def test_ambiguous_timestamp_fails():
    """Ambiguous or unparseable date strings fail timestamp normalization."""
    norm_utc, orig, is_ambig = normalize_timestamp_to_utc("invalid/date/format/999")
    assert is_ambig is True
    assert norm_utc is None


# ── 7. Currency Explicitness (No Implicit FX) ─────────────────────────

def test_currency_explicitness():
    """Non-USD currency metadata (e.g. INR) is preserved explicitly without implicit conversion."""
    contract = get_contract(DatasetType.CARGO_DEMAND)
    raw = {
        "cargo_id": "C101",
        "commodity": "Thermal Coal",
        "quantity": 65000.0,
        "origin_port_id": "IN_VIZAG",
        "destination_port_id": "IN_PRADIP",
        "laycan_start": "2026-09-10T00:00:00Z",
        "laycan_end": "2026-09-15T00:00:00Z",
        "freight_rate": 1250.0,
        "currency": "INR",
    }
    normalized, _ = normalize_record(raw, contract)
    assert normalized["currency"] == "INR"
    assert normalized["freight_rate"] == 1250.0  # Kept exactly as 1250.0 INR; no silent FX conversion


# ── 8. Duplicate Business Key Detection ────────────────────────────────

def test_duplicate_business_key_detection():
    """Duplicate business keys within a single dataset are flagged under Relational validation."""
    contract = get_contract(DatasetType.VESSEL_MASTER)
    records = [
        {"vessel_id": "V1", "vessel_name": "Vessel A", "dwt": 75000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
        {"vessel_id": "V1", "vessel_name": "Vessel Duplicate", "dwt": 80000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
    ]
    val_res, valid_recs, quar_recs = validate_dataset_records(records, contract)
    assert len(quar_recs) == 1
    assert any(iss.error_code == DataGovernanceReasonCode.DUPLICATE_RECORD for iss in val_res.issues)


# ── 9. Relational Origin != Destination Check ─────────────────────────

def test_relational_origin_destination_check():
    """Identical origin and destination ports in cargo parcel triggers relational error."""
    contract = get_contract(DatasetType.CARGO_DEMAND)
    records = [
        {
            "cargo_id": "C1",
            "commodity": "Iron Ore",
            "quantity": 120000.0,
            "origin_port_id": "PORT_A",
            "destination_port_id": "PORT_A",  # Identical
            "laycan_start": "2026-09-10T00:00:00Z",
            "laycan_end": "2026-09-15T00:00:00Z",
        }
    ]
    val_res, valid_recs, quar_recs = validate_dataset_records(records, contract)
    assert len(quar_recs) == 1
    assert any(iss.error_code == DataGovernanceReasonCode.SAME_ORIGIN_DESTINATION for iss in val_res.issues)


# ── 10. Transparent 6-Factor Quality Scoring ──────────────────────────

def test_deterministic_quality_score():
    """Known dataset produces exact deterministic 6-factor quality score."""
    contract = get_contract(DatasetType.VESSEL_MASTER)
    records = [
        {"vessel_id": "V1", "vessel_name": "Pacific Star", "dwt": 75000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
        {"vessel_id": "V2", "vessel_name": "Atlantic Hero", "dwt": 82000.0, "loa": 229.0, "beam": 32.2, "draft": 14.5, "service_speed": 14.0, "fuel_consumption": 31.0},
    ]
    val_res, _, _ = validate_dataset_records(records, contract)
    prov = {"source_name": "fleet_db", "original_filename": "fleet.csv", "original_hash": "hash_123", "import_actor": "capt_vance"}

    res = calculate_data_quality_score(records, contract, val_res, provenance_metadata=prov)
    assert res.overall_score == 83.3
    assert res.validity_score == 100.0
    assert res.consistency_score == 100.0
    assert res.uniqueness_score == 100.0
    assert res.provenance_score == 100.0


# ── 11. Freshness Classification ──────────────────────────────────────

def test_freshness_classification():
    """Freshness evaluates correctly into CURRENT, AGING, or STALE."""
    contract = get_contract(DatasetType.BUNKER_SERIES)
    now = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Current (< 24h)
    rec_current = [{"timestamp": "2026-09-06T08:00:00Z"}]
    status_curr, age_curr = evaluate_freshness(rec_current, contract, reference_time=now)
    assert status_curr == FreshnessStatus.CURRENT
    assert age_curr == pytest.approx(4.0)

    # 2. Aging (between 24h and 72h)
    rec_aging = [{"timestamp": "2026-09-04T12:00:00Z"}]
    status_aging, age_aging = evaluate_freshness(rec_aging, contract, reference_time=now)
    assert status_aging == FreshnessStatus.AGING
    assert age_aging == pytest.approx(48.0)

    # 3. Stale (> 72h)
    rec_stale = [{"timestamp": "2026-08-30T12:00:00Z"}]
    status_stale, age_stale = evaluate_freshness(rec_stale, contract, reference_time=now)
    assert status_stale == FreshnessStatus.STALE


# ── 12. SHA-256 Dataset Hash Determinism ──────────────────────────────

def test_hash_determinism():
    """Equivalent datasets produce identical canonical SHA-256 hashes regardless of dictionary key order."""
    records_a = [
        {"vessel_id": "V1", "dwt": 75000.0, "name": "Vessel A"},
        {"vessel_id": "V2", "dwt": 82000.0, "name": "Vessel B"},
    ]
    records_b = [
        {"name": "Vessel A", "vessel_id": "V1", "dwt": 75000.0},
        {"dwt": 82000.0, "vessel_id": "V2", "name": "Vessel B"},
    ]
    # Even if keys in dictionaries are created in different order
    h1 = compute_dataset_hash(records_a, "VESSEL_MASTER", 1)
    h2 = compute_dataset_hash(records_b, "VESSEL_MASTER", 1)
    assert len(h1) == 64
    assert h1 == h2


# ── 13. Record-Level Tamper Detection ─────────────────────────────────

def test_tamper_detection():
    """Altering any single field in a dataset changes its SHA-256 hash and fails integrity check."""
    records = [
        {"vessel_id": "V1", "dwt": 75000.0, "name": "Vessel A"},
    ]
    original_hash = compute_dataset_hash(records, "VESSEL_MASTER", 1)

    # Tamper with DWT
    tampered_records = [
        {"vessel_id": "V1", "dwt": 75001.0, "name": "Vessel A"},
    ]
    is_valid = verify_dataset_integrity(tampered_records, "VESSEL_MASTER", 1, original_hash)
    assert is_valid is False


# ── 14. Dataset Versioning (V1 -> V2) ─────────────────────────────────

def test_dataset_versioning(db_session):
    """Importing V2 increments current_version without mutating historical V1 records."""
    service = DataGovernanceService(db_session)
    v1_recs = [
        {"vessel_id": "V1", "vessel_name": "Pacific Star", "dwt": 75000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
    ]
    ds = service.import_dataset(
        dataset_type=DatasetType.VESSEL_MASTER,
        name="Versioned Fleet",
        source_payload=v1_recs,
    )
    ds_id = ds["dataset_id"]
    service.approve_dataset(ds_id)

    # Import V2
    v2_recs = [
        {"vessel_id": "V1", "vessel_name": "Pacific Star", "dwt": 78000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
    ]
    v2_res = service.import_new_version(
        dataset_id=ds_id,
        source_payload=v2_recs,
        change_summary="Upgraded cargo holds (+3,000 MT DWT).",
    )
    assert v2_res["version_number"] == 2
    assert v2_res["modified_count"] == 1

    # Verify both V1 and V2 records exist in database
    db_recs = db_session.query(DatasetRecord).join(GovernanceDataset).filter(GovernanceDataset.dataset_id == ds_id).all()
    versions_found = {r.version_number for r in db_recs}
    assert 1 in versions_found
    assert 2 in versions_found


# ── 15. Dataset Diff Engine (ADDED, REMOVED, MODIFIED, UNCHANGED) ─────

def test_dataset_diff_engine():
    """Diff engine accurately categorizes ADDED, REMOVED, MODIFIED, and UNCHANGED records."""
    base_recs = [
        {"vessel_id": "V1", "dwt": 75000.0, "name": "V1"},
        {"vessel_id": "V2", "dwt": 82000.0, "name": "V2"},
        {"vessel_id": "V3", "dwt": 55000.0, "name": "V3"},
    ]
    target_recs = [
        {"vessel_id": "V1", "dwt": 78000.0, "name": "V1"},  # MODIFIED
        {"vessel_id": "V2", "dwt": 82000.0, "name": "V2"},  # UNCHANGED
        {"vessel_id": "V4", "dwt": 95000.0, "name": "V4"},  # ADDED
        # V3 is REMOVED
    ]
    diff = compare_datasets("DS-TEST", base_recs, target_recs, ("vessel_id",), 1, 2)
    assert diff.added_count == 1
    assert diff.removed_count == 1
    assert diff.modified_count == 1
    assert diff.unchanged_count == 1


# ── 16. Quarantine Ledger Retention ───────────────────────────────────

def test_quarantine_retention(db_session):
    """Quarantined records are persisted with exact field, error code, and original value."""
    service = DataGovernanceService(db_session)
    records = [
        {"vessel_id": "V1", "vessel_name": "Defective Vessel", "dwt": -50000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
    ]
    ds = service.import_dataset(
        dataset_type=DatasetType.VESSEL_MASTER,
        name="Quarantine Test",
        source_payload=records,
    )
    quar_list = service.get_quarantine_records(ds["dataset_id"])
    assert len(quar_list) == 1
    assert quar_list[0]["error_code"] == "NEGATIVE_PHYSICAL_VALUE"
    assert quar_list[0]["field_name"] == "dwt"
    assert quar_list[0]["original_value"] == "-50000.0"


# ── 17. Dataset Approval Workflow ─────────────────────────────────────

def test_dataset_approval_workflow(db_session):
    """Only VALID datasets can be APPROVED; invalid/quarantined raise error."""
    service = DataGovernanceService(db_session)
    # 1. Valid dataset approval
    valid_recs = [
        {"vessel_id": "V1", "vessel_name": "Valid Vessel", "dwt": 75000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
    ]
    ds_valid = service.import_dataset(DatasetType.VESSEL_MASTER, "Approve Test", valid_recs)
    app_ds = service.approve_dataset(ds_valid["dataset_id"], actor="director_bob")
    assert app_ds["status"] == "APPROVED"
    assert app_ds["approved_by"] == "director_bob"

    # 2. Quarantined dataset approval must fail
    bad_recs = [
        {"vessel_id": "V2", "vessel_name": "Bad Vessel", "dwt": -100.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
    ]
    ds_bad = service.import_dataset(DatasetType.VESSEL_MASTER, "Bad Fleet", bad_recs)
    with pytest.raises(ValueError, match="Cannot approve dataset in status"):
        service.approve_dataset(ds_bad["dataset_id"])


# ── 18. Downstream Dependency Impact Analyzer ─────────────────────────

def test_downstream_impact_analysis():
    """Vessel master changes identify affected downstream engines across Phases 4–11."""
    diff = compare_datasets("DS-V", [], [{"vessel_id": "V1"}], ("vessel_id",), 1, 2)
    impact = analyze_dataset_impact("DS-V", DatasetType.VESSEL_MASTER, 2, diff_result=diff)
    assert impact.impact_level in (ImpactLevel.HIGH, ImpactLevel.CRITICAL)
    assert impact.requires_recalculation is True
    assert any("Phase 4" in eng for eng in impact.affected_engines)
    assert any("Phase 7" in eng for eng in impact.affected_engines)


# ── 19. Stale Decision Package Detection (Phase 11 Integration) ───────

def test_stale_decision_detection(db_session):
    """Superseding a dataset marks dependent Phase 11 Decision Packages STALE_INPUT without mutating them."""
    gov_service = GovernanceService(db_session)
    data_service = DataGovernanceService(db_session)

    # 1. Seed demo DecisionPackage in Phase 11
    pkg = gov_service.get_or_create_demo_package(scenario_type="BASELINE")
    pkg_id = pkg["package_id"]

    # 2. Seed and update vessel master
    ds = data_service.seed_canonical_demo_data()
    impact = data_service.get_dataset_impact(ds["dataset_id"])
    assert impact is not None
    assert pkg_id in impact["stale_decision_packages"]

    # Verify historical Decision Package status is still intact
    refreshed_pkg = gov_service.get_package(pkg_id)
    assert refreshed_pkg["status"] == "APPROVED"  # Historical package remains immutable


# ── 20. Audit Event Logging ───────────────────────────────────────────

def test_audit_event_logging(db_session):
    """Ingestion and approval actions produce verifiable audit records."""
    service = DataGovernanceService(db_session)
    records = [
        {"vessel_id": "V1", "vessel_name": "Audit Test", "dwt": 75000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
    ]
    ds = service.import_dataset(DatasetType.VESSEL_MASTER, "Audit Fleet", records)
    prov = db_session.query(DatasetProvenance).join(GovernanceDataset).filter(GovernanceDataset.dataset_id == ds["dataset_id"]).first()
    assert prov is not None
    assert prov.import_actor == "data_engineer"


# ── 21. REST API Endpoint Lifecycle ───────────────────────────────────

def test_data_api_lifecycle(client):
    """End-to-end API test: import -> get -> approve -> import version -> diff -> impact."""
    # 1. Import
    imp_resp = client.post(
        "/v1/data/import",
        json={
            "dataset_type": "VESSEL_MASTER",
            "name": "API Vessel Fleet",
            "records": [
                {"vessel_id": "V1", "vessel_name": "API Star", "dwt": 75000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
            ],
            "actor": "api_tester",
        },
    )
    assert imp_resp.status_code == 200
    ds_id = imp_resp.json()["dataset_id"]

    # 2. Get details
    get_resp = client.get(f"/v1/data/datasets/{ds_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["dataset_id"] == ds_id

    # 3. Approve
    app_resp = client.post(
        f"/v1/data/datasets/{ds_id}/approve",
        json={"actor": "director_bob", "actor_role": "APPROVER"},
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"

    # 4. Import Version 2
    v2_resp = client.post(
        f"/v1/data/datasets/{ds_id}/version",
        json={
            "records": [
                {"vessel_id": "V1", "vessel_name": "API Star", "dwt": 78000.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
            ],
            "change_summary": "Revised DWT via API",
            "actor": "api_tester",
        },
    )
    assert v2_resp.status_code == 200
    assert v2_resp.json()["version_number"] == 2

    # 5. Get Diff
    diff_resp = client.get(f"/v1/data/datasets/{ds_id}/diff")
    assert diff_resp.status_code == 200
    assert diff_resp.json()["total_changes"] == 1

    # 6. Get Impact
    impact_resp = client.get(f"/v1/data/datasets/{ds_id}/impact")
    assert impact_resp.status_code == 200
    assert impact_resp.json()["requires_recalculation"] is True


# ── 22. SQLite Persistence & Transaction Integrity ────────────────────

def test_sqlite_persistence(db_session):
    """Database models persist correctly with foreign keys and relationships."""
    ds = GovernanceDataset(
        dataset_id="DS-TEST-SQLITE",
        dataset_type="VESSEL_MASTER",
        name="Test SQLite",
        content_hash="hash_sqlite_123",
        created_by="tester",
    )
    db_session.add(ds)
    db_session.commit()

    retrieved = db_session.query(GovernanceDataset).filter(GovernanceDataset.dataset_id == "DS-TEST-SQLITE").first()
    assert retrieved is not None
    assert retrieved.name == "Test SQLite"


# ── 23. Quarantine API Endpoint ───────────────────────────────────────

def test_quarantine_api_endpoint(client):
    """Quarantine endpoint returns defect records."""
    imp_resp = client.post(
        "/v1/data/import",
        json={
            "dataset_type": "VESSEL_MASTER",
            "name": "API Quarantine Fleet",
            "records": [
                {"vessel_id": "V1", "vessel_name": "Broken Vessel", "dwt": -100.0, "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0},
            ],
            "actor": "api_tester",
        },
    )
    assert imp_resp.status_code == 200
    ds_id = imp_resp.json()["dataset_id"]

    quar_resp = client.get(f"/v1/data/datasets/{ds_id}/quarantine")
    assert quar_resp.status_code == 200
    assert len(quar_resp.json()) >= 1


# ── 24. Air-Gap Compliance ────────────────────────────────────────────

def test_air_gap_compliance(monkeypatch):
    """Phase 12 data governance makes zero outbound socket connections."""
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Air-gap violation: socket connection attempted in Phase 12!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    # Ingestion and normalization must work purely offline
    contract = get_contract(DatasetType.VESSEL_MASTER)
    records = [{"vessel_id": "V1", "dwt": "75,000 MT", "loa": 225.0, "beam": 32.2, "draft": 14.2, "service_speed": 13.5, "fuel_consumption": 28.0, "vessel_name": "AirGap Vessel"}]
    norm_rec, _ = normalize_record(records[0], contract)
    val_res, _, _ = validate_dataset_records([norm_rec], contract)
    assert val_res.is_valid is True
    h = compute_dataset_hash([norm_rec], "VESSEL_MASTER", 1)
    assert len(h) == 64


# ── 25. Full Regression Integrity ─────────────────────────────────────

def test_canonical_demo_data_seeding(db_session):
    """Canonical demo seeding per Section 33 produces V1 and V2 datasets."""
    service = DataGovernanceService(db_session)
    demo_ds = service.seed_canonical_demo_data()
    assert demo_ds["dataset_id"] == "DS-VESSEL-MASTER-DEMO"
    assert demo_ds["current_version"] == 2
    assert demo_ds["record_count"] == 5
