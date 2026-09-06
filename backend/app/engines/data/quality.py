"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Transparent 6-Factor Quality Scoring & Freshness Engine
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.engines.data.contracts import DatasetContract
from app.engines.data.models import QualityScoreResult, ValidationResult
from app.engines.data.reason_codes import FreshnessStatus


DEFAULT_QUALITY_WEIGHTS: Dict[str, float] = {
    "completeness": 0.25,
    "validity": 0.25,
    "consistency": 0.20,
    "uniqueness": 0.10,
    "timeliness": 0.10,
    "provenance": 0.10,
}


def evaluate_freshness(
    records: List[Dict[str, Any]],
    contract: DatasetContract,
    reference_time: Optional[datetime] = None,
) -> Tuple[FreshnessStatus, Optional[float]]:
    """
    Evaluates dataset freshness against contract thresholds.
    Returns:
        (FreshnessStatus, age_in_hours)
    """
    now = reference_time or datetime.now(timezone.utc)

    # Search for latest timestamp in records
    latest_dt: Optional[datetime] = None
    for r in records:
        for f_name, f_contract in contract.fields.items():
            if f_contract.field_type == "datetime":
                v = r.get(f_name)
                if v:
                    try:
                        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
                        if latest_dt is None or dt > latest_dt:
                            latest_dt = dt
                    except Exception:
                        pass

    if not latest_dt:
        return FreshnessStatus.UNKNOWN, None

    if latest_dt.tzinfo is None:
        latest_dt = latest_dt.replace(tzinfo=timezone.utc)

    age_hours = max(0.0, (now - latest_dt).total_seconds() / 3600.0)

    if age_hours <= contract.freshness_hours_current:
        status = FreshnessStatus.CURRENT
    elif age_hours <= contract.freshness_hours_aging:
        status = FreshnessStatus.AGING
    else:
        status = FreshnessStatus.STALE

    return status, age_hours


def calculate_data_quality_score(
    records: List[Dict[str, Any]],
    contract: DatasetContract,
    validation_result: ValidationResult,
    provenance_metadata: Optional[Dict[str, Any]] = None,
    custom_weights: Optional[Dict[str, float]] = None,
    reference_time: Optional[datetime] = None,
) -> QualityScoreResult:
    """
    Computes a transparent, auditable [0, 100] Data Quality Score.
    """
    weights = custom_weights or DEFAULT_QUALITY_WEIGHTS
    total_records = len(records)
    if total_records == 0:
        return QualityScoreResult(
            overall_score=0.0,
            completeness_score=0.0,
            validity_score=0.0,
            consistency_score=0.0,
            uniqueness_score=0.0,
            timeliness_score=0.0,
            provenance_score=0.0,
            weights=weights,
            freshness_status=FreshnessStatus.UNKNOWN,
            freshness_age_hours=None,
            evaluated_at=datetime.now(timezone.utc),
        )

    # 1. Completeness Score (0 - 100)
    # Ratio of non-null values across all contracted fields
    total_field_slots = total_records * len(contract.fields)
    populated_slots = 0
    for r in records:
        for f_name in contract.fields.keys():
            v = r.get(f_name)
            if v is not None and str(v).strip() != "":
                populated_slots += 1
    completeness = round((populated_slots / max(1, total_field_slots)) * 100.0, 1)

    # 2. Validity Score (0 - 100)
    # Percentage of records passing physical and type rules
    valid_count = validation_result.valid_records_count
    validity = round((valid_count / total_records) * 100.0, 1)

    # 3. Consistency Score (0 - 100)
    # Checks for absence of relational and structural layer errors
    relational_errors = sum(1 for iss in validation_result.issues if iss.layer.value == "RELATIONAL")
    structural_errors = sum(1 for iss in validation_result.issues if iss.layer.value == "STRUCTURAL")
    inconsistent_records = min(total_records, relational_errors + structural_errors)
    consistency = round(max(0.0, (1.0 - (inconsistent_records / total_records))) * 100.0, 1)

    # 4. Uniqueness Score (0 - 100)
    b_keys = set()
    dup_count = 0
    for idx, r in enumerate(records):
        parts = [str(r.get(k, "")) for k in contract.business_key_fields if r.get(k) is not None]
        k_str = ":".join(parts) if parts else f"ROW-{idx}"
        if k_str in b_keys:
            dup_count += 1
        else:
            b_keys.add(k_str)
    uniqueness = round(max(0.0, (1.0 - (dup_count / total_records))) * 100.0, 1)

    # 5. Timeliness Score (0 - 100)
    freshness_status, age_hours = evaluate_freshness(records, contract, reference_time=reference_time)
    if freshness_status == FreshnessStatus.CURRENT:
        timeliness = 100.0
    elif freshness_status == FreshnessStatus.AGING:
        timeliness = 70.0
    elif freshness_status == FreshnessStatus.STALE:
        timeliness = 40.0
    else:
        timeliness = 50.0

    # 6. Provenance Score (0 - 100)
    prov = provenance_metadata or {}
    prov_pts = 0
    if prov.get("source_name"):
        prov_pts += 25
    if prov.get("original_filename"):
        prov_pts += 25
    if prov.get("original_hash"):
        prov_pts += 25
    if prov.get("import_actor"):
        prov_pts += 25
    provenance_score = float(prov_pts)

    # Weighted Composite Score
    overall = (
        completeness * weights.get("completeness", 0.25)
        + validity * weights.get("validity", 0.25)
        + consistency * weights.get("consistency", 0.20)
        + uniqueness * weights.get("uniqueness", 0.10)
        + timeliness * weights.get("timeliness", 0.10)
        + provenance_score * weights.get("provenance", 0.10)
    )
    overall_clamped = round(max(0.0, min(100.0, overall)), 1)

    return QualityScoreResult(
        overall_score=overall_clamped,
        completeness_score=completeness,
        validity_score=validity,
        consistency_score=consistency,
        uniqueness_score=uniqueness,
        timeliness_score=timeliness,
        provenance_score=provenance_score,
        weights=weights,
        freshness_status=freshness_status,
        freshness_age_hours=round(age_hours, 1) if age_hours is not None else None,
        evaluated_at=datetime.now(timezone.utc),
    )
