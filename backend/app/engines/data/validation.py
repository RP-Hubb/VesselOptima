"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Four-Tier Validation Engine (Structural, Type, Physical & Relational)
"""

from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

from app.engines.data.contracts import DatasetContract
from app.engines.data.models import FieldValidationIssue, ValidationResult
from app.engines.data.normalization import normalize_timestamp_to_utc
from app.engines.data.reason_codes import (
    DataGovernanceReasonCode,
    QuarantineSeverity,
    ValidationLayer,
)


def validate_dataset_records(
    records: List[Dict[str, Any]],
    contract: DatasetContract,
) -> Tuple[ValidationResult, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Executes the 4-tier validation pipeline across all normalized records.
    Returns:
        Tuple of:
          - ValidationResult (summary metrics, issues list, layer results)
          - valid_records (records passing all critical checks)
          - quarantined_records (records failing physical or critical relational rules)
    """
    issues: List[FieldValidationIssue] = []
    layer_status: Dict[str, bool] = {
        ValidationLayer.STRUCTURAL.value: True,
        ValidationLayer.TYPE.value: True,
        ValidationLayer.PHYSICAL.value: True,
        ValidationLayer.RELATIONAL.value: True,
    }

    valid_records: List[Dict[str, Any]] = []
    quarantined_records: List[Dict[str, Any]] = []

    # Track seen business keys for uniqueness check
    seen_business_keys: Set[str] = set()

    for idx, record in enumerate(records):
        row_has_rejection = False
        row_has_quarantine = False

        # Extract business key string
        b_key_parts = [str(record.get(k, "")) for k in contract.business_key_fields if record.get(k) is not None]
        business_key = ":".join(b_key_parts) if b_key_parts else f"ROW-{idx}"

        # ── LAYER 1: STRUCTURAL VALIDATION ────────────────────────────
        for field_name, f_contract in contract.fields.items():
            if f_contract.required:
                val = record.get(field_name)
                if val is None or (isinstance(val, str) and str(val).strip() == ""):
                    issues.append(
                        FieldValidationIssue(
                            record_index=idx,
                            business_key=business_key,
                            field_name=field_name,
                            original_value=val,
                            layer=ValidationLayer.STRUCTURAL,
                            error_code=DataGovernanceReasonCode.MISSING_REQUIRED_FIELD,
                            severity=QuarantineSeverity.DATASET_REJECTION,
                            message=f"Mandatory contract field '{field_name}' is missing or empty.",
                        )
                    )
                    layer_status[ValidationLayer.STRUCTURAL.value] = False
                    row_has_rejection = True

        # ── LAYER 2: TYPE & UNIT VALIDATION ───────────────────────────
        for field_name, f_contract in contract.fields.items():
            val = record.get(field_name)
            if val is None:
                continue

            if f_contract.field_type in ("float", "integer"):
                if not isinstance(val, (int, float)):
                    issues.append(
                        FieldValidationIssue(
                            record_index=idx,
                            business_key=business_key,
                            field_name=field_name,
                            original_value=val,
                            layer=ValidationLayer.TYPE,
                            error_code=DataGovernanceReasonCode.TYPE_MISMATCH,
                            severity=QuarantineSeverity.ROW_QUARANTINE,
                            message=f"Field '{field_name}' expected {f_contract.field_type}, got '{type(val).__name__}'.",
                        )
                    )
                    layer_status[ValidationLayer.TYPE.value] = False
                    row_has_quarantine = True

            elif f_contract.field_type == "datetime":
                norm_utc, orig, is_ambiguous = normalize_timestamp_to_utc(val)
                if is_ambiguous or not norm_utc:
                    issues.append(
                        FieldValidationIssue(
                            record_index=idx,
                            business_key=business_key,
                            field_name=field_name,
                            original_value=val,
                            layer=ValidationLayer.TYPE,
                            error_code=DataGovernanceReasonCode.AMBIGUOUS_TIMESTAMP,
                            severity=QuarantineSeverity.ROW_QUARANTINE,
                            message=f"Field '{field_name}' contains unparseable or ambiguous timestamp '{val}'.",
                        )
                    )
                    layer_status[ValidationLayer.TYPE.value] = False
                    row_has_quarantine = True

        # ── LAYER 3: PHYSICAL MARITIME CONSTRAINTS ────────────────────
        for field_name, f_contract in contract.fields.items():
            val = record.get(field_name)
            if val is not None and isinstance(val, (int, float)):
                # Min bound check
                if f_contract.min_value is not None and val < f_contract.min_value:
                    rc = (
                        DataGovernanceReasonCode.NEGATIVE_PHYSICAL_VALUE
                        if val < 0
                        else DataGovernanceReasonCode.PHYSICAL_BOUNDS_VERIFIED
                    )
                    issues.append(
                        FieldValidationIssue(
                            record_index=idx,
                            business_key=business_key,
                            field_name=field_name,
                            original_value=val,
                            layer=ValidationLayer.PHYSICAL,
                            error_code=rc if val < 0 else DataGovernanceReasonCode.ZERO_SPEED_OR_CONSUMPTION,
                            severity=QuarantineSeverity.ROW_QUARANTINE,
                            message=f"Physical bound violation on '{field_name}': value {val} < minimum {f_contract.min_value}.",
                        )
                    )
                    layer_status[ValidationLayer.PHYSICAL.value] = False
                    row_has_quarantine = True

                # Max bound check
                if f_contract.max_value is not None and val > f_contract.max_value:
                    issues.append(
                        FieldValidationIssue(
                            record_index=idx,
                            business_key=business_key,
                            field_name=field_name,
                            original_value=val,
                            layer=ValidationLayer.PHYSICAL,
                            error_code=DataGovernanceReasonCode.COORDINATES_OUT_OF_BOUNDS if "lat" in field_name or "lon" in field_name else DataGovernanceReasonCode.EXCESSIVE_DRAFT,
                            severity=QuarantineSeverity.ROW_QUARANTINE,
                            message=f"Physical bound violation on '{field_name}': value {val} > maximum {f_contract.max_value}.",
                        )
                    )
                    layer_status[ValidationLayer.PHYSICAL.value] = False
                    row_has_quarantine = True

        # ── LAYER 4: RELATIONAL & CROSS-FIELD CONSTRAINTS ─────────────
        # 1. Duplicate business key check
        if business_key:
            if business_key in seen_business_keys:
                issues.append(
                    FieldValidationIssue(
                        record_index=idx,
                        business_key=business_key,
                        field_name="business_key",
                        original_value=business_key,
                        layer=ValidationLayer.RELATIONAL,
                        error_code=DataGovernanceReasonCode.DUPLICATE_RECORD,
                        severity=QuarantineSeverity.ROW_QUARANTINE,
                        message=f"Duplicate business key '{business_key}' detected in dataset.",
                    )
                )
                layer_status[ValidationLayer.RELATIONAL.value] = False
                row_has_quarantine = True
            else:
                seen_business_keys.add(business_key)

        # 2. Origin != Destination check (Cargo and Voyage)
        origin = record.get("origin_port_id")
        destination = record.get("destination_port_id")
        if origin and destination and str(origin).strip() == str(destination).strip():
            issues.append(
                FieldValidationIssue(
                    record_index=idx,
                    business_key=business_key,
                    field_name="destination_port_id",
                    original_value=destination,
                    layer=ValidationLayer.RELATIONAL,
                    error_code=DataGovernanceReasonCode.SAME_ORIGIN_DESTINATION,
                    severity=QuarantineSeverity.ROW_QUARANTINE,
                    message=f"Relational violation: origin and destination ports are identical ('{origin}').",
                )
            )
            layer_status[ValidationLayer.RELATIONAL.value] = False
            row_has_quarantine = True

        # 3. Laycan window start <= end check
        ls = record.get("laycan_start")
        le = record.get("laycan_end")
        if ls and le:
            try:
                dt_start = datetime.fromisoformat(str(ls).replace("Z", "+00:00"))
                dt_end = datetime.fromisoformat(str(le).replace("Z", "+00:00"))
                if dt_start > dt_end:
                    issues.append(
                        FieldValidationIssue(
                            record_index=idx,
                            business_key=business_key,
                            field_name="laycan_start",
                            original_value=f"{ls} > {le}",
                            layer=ValidationLayer.RELATIONAL,
                            error_code=DataGovernanceReasonCode.INVERTED_LAYCAN_WINDOW,
                            severity=QuarantineSeverity.ROW_QUARANTINE,
                            message=f"Laycan start ({ls}) cannot be after laycan end ({le}).",
                        )
                    )
                    layer_status[ValidationLayer.RELATIONAL.value] = False
                    row_has_quarantine = True
            except Exception:
                pass

        # Segregation into valid vs quarantined
        if row_has_rejection or row_has_quarantine:
            quarantined_records.append(record)
        else:
            valid_records.append(record)

    is_overall_valid = len(quarantined_records) == 0 and not any(
        iss.severity == QuarantineSeverity.DATASET_REJECTION for iss in issues
    )

    val_result = ValidationResult(
        is_valid=is_overall_valid,
        total_records=len(records),
        valid_records_count=len(valid_records),
        quarantined_records_count=len(quarantined_records),
        rejected_records_count=sum(1 for iss in issues if iss.severity == QuarantineSeverity.DATASET_REJECTION),
        layer_results=layer_status,
        issues=issues,
    )

    return val_result, valid_records, quarantined_records
