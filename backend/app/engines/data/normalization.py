"""
VesselOptima — Phase 12 Maritime Data Integration & Quality Governance
Data Normalization, Explicit Unit Governance & Timestamp UTC Conversion
"""

import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.engines.data.contracts import DatasetContract, FieldContract


def normalize_numeric_string(raw_val: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Parses numeric strings with embedded commas and units (e.g. '70,000 MT', '13.5 kts').
    Returns (numeric_value, detected_unit).
    """
    if raw_val is None:
        return None, None
    if isinstance(raw_val, (int, float)):
        return float(raw_val), None

    s = str(raw_val).strip()
    if not s:
        return None, None

    # Regex to capture numeric component and potential unit suffix
    match = re.match(r"^([+-]?[\d,]+(?:\.\d+)?)\s*([A-Za-z/]+)?$", s)
    if not match:
        try:
            return float(s.replace(",", "")), None
        except ValueError:
            return None, None

    num_part = match.group(1).replace(",", "")
    unit_part = match.group(2)

    try:
        val = float(num_part)
        clean_unit = unit_part.strip() if unit_part else None
        return val, clean_unit
    except ValueError:
        return None, None


def normalize_timestamp_to_utc(raw_val: Any) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Normalizes diverse timestamp formats to strict ISO8601 UTC representation.
    Returns:
        Tuple of (normalized_iso_utc, original_string, is_ambiguous_failure)
    """
    if raw_val is None:
        return None, None, False

    s = str(raw_val).strip()
    if not s:
        return None, s, False

    # Check for ambiguous date without year or invalid strings
    if len(s) < 8 or ("/" in s and len(s.split("/")) != 3):
        return None, s, True

    # 1. Try standard ISO parsing
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            # Native timestamp without timezone
            dt_utc = dt.replace(tzinfo=timezone.utc)
        else:
            dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.isoformat(), s, False
    except Exception:
        pass

    # 2. Try common maritime date formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            dt_utc = dt.replace(tzinfo=timezone.utc)
            return dt_utc.isoformat(), s, False
        except ValueError:
            continue

    # Unparseable or ambiguous
    return None, s, True


def normalize_record(
    raw_record: Dict[str, Any],
    contract: DatasetContract,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Normalizes a single record per the authoritative DatasetContract:
    - Strips whitespace
    - Casts types
    - Cleans units
    - Converts timestamps to UTC
    - Preserves explicit currency metadata without implicit conversion
    Returns:
        (normalized_record_dict, list_of_transformations_applied)
    """
    normalized: Dict[str, Any] = {}
    transformations: List[Dict[str, Any]] = []

    for field_name, f_contract in contract.fields.items():
        if field_name not in raw_record:
            continue

        raw_val = raw_record[field_name]
        if raw_val is None or (isinstance(raw_val, str) and raw_val.strip() == ""):
            normalized[field_name] = None
            continue

        # String stripping
        if isinstance(raw_val, str):
            raw_val = raw_val.strip()

        # Type-specific normalization
        if f_contract.field_type in ("float", "integer"):
            num_val, extracted_unit = normalize_numeric_string(raw_val)
            if num_val is not None:
                final_val = int(round(num_val)) if f_contract.field_type == "integer" else num_val
                normalized[field_name] = final_val
                if str(final_val) != str(raw_val):
                    transformations.append({
                        "field": field_name,
                        "from": raw_val,
                        "to": final_val,
                        "type": "NUMERIC_PARSE",
                    })
                if extracted_unit:
                    normalized[f"{field_name}_unit"] = extracted_unit
            else:
                normalized[field_name] = raw_val

        elif f_contract.field_type == "datetime":
            norm_utc, orig, is_ambiguous = normalize_timestamp_to_utc(raw_val)
            if norm_utc and not is_ambiguous:
                normalized[field_name] = norm_utc
                transformations.append({
                    "field": field_name,
                    "from": raw_val,
                    "to": norm_utc,
                    "type": "TIMESTAMP_UTC_NORMALIZE",
                })
            else:
                normalized[field_name] = raw_val

        elif f_contract.field_type == "boolean":
            s_low = str(raw_val).lower().strip()
            b_val = s_low in ("true", "1", "yes", "t", "y")
            normalized[field_name] = b_val
            if str(b_val) != str(raw_val):
                transformations.append({
                    "field": field_name,
                    "from": raw_val,
                    "to": b_val,
                    "type": "BOOLEAN_CAST",
                })
        else:
            # String field
            s_val = str(raw_val).strip()
            normalized[field_name] = s_val

    # Explicit currency metadata preservation (e.g. freight_rate currency or price currency)
    currency_val = raw_record.get("currency") or contract.default_currency
    normalized["currency"] = str(currency_val).upper().strip()

    # Pass through uncontracted extra fields safely
    for k, v in raw_record.items():
        if k not in normalized and not k.endswith("_unit"):
            normalized[k] = v

    return normalized, transformations
