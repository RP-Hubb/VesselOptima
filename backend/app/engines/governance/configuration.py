"""
VesselOptima — Phase 11 Decision Governance & Institutional Control
Policy Configuration & Change Auditing Engine
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from app.engines.governance.hashing import compute_canonical_hash


def get_default_decision_configuration() -> Dict[str, Any]:
    """Returns baseline institutional decision policy configuration."""
    cfg = {
        "configuration_id": "CONFIG-INSTITUTIONAL-V1",
        "version": "1.0.0",
        "name": "Standard Institutional Fleet Allocation Policy",
        "description": "Authoritative institutional weighting and hurdle thresholds for fleet chartering.",
        "status": "ACTIVE",
        "economic_weight": 0.35,
        "reliability_weight": 0.25,
        "robustness_weight": 0.20,
        "tail_risk_weight": 0.10,
        "schedule_weight": 0.10,
        "recommendation_thresholds": {
            "min_score_proceed": 75.0,
            "min_score_caution": 50.0,
            "max_loss_prob_proceed": 0.05,
            "max_loss_prob_caution": 0.15,
            "max_cvar95_downside_ratio_proceed": 0.20,
            "min_reliability_proceed": 80.0,
        },
        "confidence_thresholds": {
            "min_simulation_count_high": 1000,
            "min_stability_high": 0.80,
            "min_stability_medium": 0.50,
        },
        "risk_thresholds": {
            "risk_aversion_lambda": 0.50,
            "min_schedule_buffer_days": 2.0,
            "max_laycan_miss_prob_proceed": 0.05,
        },
        "effective_date": "2026-09-06T00:00:00Z",
    }
    cfg["config_hash"] = compute_canonical_hash(cfg)
    return cfg


def build_configuration_change(
    old_config: Dict[str, Any],
    new_config: Dict[str, Any],
    reason: str,
    actor: str,
    actor_role: str = "ADMIN",
) -> Dict[str, Any]:
    """
    Computes field-by-field diff between old and new configuration versions
    and builds an auditable ConfigurationChange record.
    """
    changed_fields: Dict[str, Dict[str, Any]] = {}

    all_keys = set(old_config.keys()).union(set(new_config.keys()))
    for k in all_keys:
        if k in ("config_hash", "status", "effective_date"):
            continue
        old_val = old_config.get(k)
        new_val = new_config.get(k)
        if old_val != new_val:
            changed_fields[k] = {"old": old_val, "new": new_val}

    return {
        "change_id": f"CHG-{uuid4().hex[:8].upper()}",
        "old_configuration_id": old_config.get("configuration_id"),
        "new_configuration_id": new_config.get("configuration_id"),
        "changed_fields": changed_fields,
        "reason": reason,
        "actor": actor,
        "actor_role": actor_role,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
