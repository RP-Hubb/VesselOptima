"""
VesselOptima — Procurement Lead-Time Model
Follows Section 5 of the Phase 5 Specification.

Lead time is computed as the sum of explicit, configurable administrative stages:
tau_procurement = tender_prep + bid_submission + tech_eval + comm_eval + approval + award
No hardcoded legal claims.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ProcurementProfile:
    profile_id: str
    name: str
    tender_preparation_days: float
    bid_submission_days: float
    technical_evaluation_days: float
    commercial_evaluation_days: float
    approval_days: float
    award_days: float
    description: str
    data_classification: str = "CONFIGURED"
    is_active: bool = True

    @property
    def minimum_lead_time_days(self) -> float:
        """Computes minimum lead time as exact sum of all operational procurement stages."""
        return (
            self.tender_preparation_days
            + self.bid_submission_days
            + self.technical_evaluation_days
            + self.commercial_evaluation_days
            + self.approval_days
            + self.award_days
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["minimum_lead_time_days"] = self.minimum_lead_time_days
        return data


# Standard Built-in Procurement Profiles
DEFAULT_PROFILES: Dict[str, ProcurementProfile] = {
    "STANDARD_COMMERCIAL": ProcurementProfile(
        profile_id="STANDARD_COMMERCIAL",
        name="Standard Commercial Tender",
        tender_preparation_days=3.0,
        bid_submission_days=5.0,
        technical_evaluation_days=2.0,
        commercial_evaluation_days=2.0,
        approval_days=1.0,
        award_days=1.0,
        description="Standard commercial chartering tender process (14 days total lead time).",
        data_classification="CONFIGURED",
    ),
    "STRICT_GOVERNMENT": ProcurementProfile(
        profile_id="STRICT_GOVERNMENT",
        name="Strict Government / Public Enterprise Tender",
        tender_preparation_days=5.0,
        bid_submission_days=7.0,
        technical_evaluation_days=3.0,
        commercial_evaluation_days=3.0,
        approval_days=2.0,
        award_days=1.0,
        description="Formal public enterprise procurement compliance tender (21 days total lead time).",
        data_classification="CONFIGURED",
    ),
    "EXPEDITED_SPOT": ProcurementProfile(
        profile_id="EXPEDITED_SPOT",
        name="Expedited Spot Chartering",
        tender_preparation_days=1.0,
        bid_submission_days=1.0,
        technical_evaluation_days=0.5,
        commercial_evaluation_days=0.5,
        approval_days=0.5,
        award_days=0.5,
        description="Fast-track direct spot market chartering fixing (4 days total lead time).",
        data_classification="CONFIGURED",
    ),
}


def get_procurement_profile(
    profile_id: Optional[str] = None,
    custom_stages: Optional[Dict[str, float]] = None,
) -> ProcurementProfile:
    """
    Resolves procurement profile.
    If custom_stages is provided, applies overrides over the base profile.
    """
    key = profile_id.upper() if profile_id else "STANDARD_COMMERCIAL"
    base = DEFAULT_PROFILES.get(key, DEFAULT_PROFILES["STANDARD_COMMERCIAL"])

    if not custom_stages:
        return base

    assigned_id = f"{key}_CUSTOM" if key in DEFAULT_PROFILES else key
    name = (
        custom_stages.get("name")
        or (f"{base.name} (Custom Overrides)" if key in DEFAULT_PROFILES else profile_id)
    )

    return ProcurementProfile(
        profile_id=assigned_id,
        name=name,
        tender_preparation_days=float(custom_stages.get("tender_preparation_days", base.tender_preparation_days)),
        bid_submission_days=float(custom_stages.get("bid_submission_days", base.bid_submission_days)),
        technical_evaluation_days=float(custom_stages.get("technical_evaluation_days", base.technical_evaluation_days)),
        commercial_evaluation_days=float(custom_stages.get("commercial_evaluation_days", base.commercial_evaluation_days)),
        approval_days=float(custom_stages.get("approval_days", base.approval_days)),
        award_days=float(custom_stages.get("award_days", base.award_days)),
        description="User-configured procurement stage durations.",
        data_classification="ASSUMPTION",
    )
