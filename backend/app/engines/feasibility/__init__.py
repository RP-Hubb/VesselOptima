"""
VesselOptima — Feasibility Engine
Evaluates operational, physical, and temporal constraints for vessel-cargo-route assignments.
Core Principle: Feasibility != Optimization (Prediction != Decision).
"""

from app.engines.feasibility.reason_codes import FeasibilityReasonCode
from app.engines.feasibility.service import FeasibilityService

__all__ = ["FeasibilityReasonCode", "FeasibilityService"]
