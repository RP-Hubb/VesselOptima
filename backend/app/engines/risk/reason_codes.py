"""
VesselOptima — Phase 9: Risk Intelligence Reason Codes & Enums

Defines standardized reason codes, risk classification tiers, provenance classifications,
and distribution definitions for stochastic risk quantification.
"""

from __future__ import annotations

from enum import Enum


class RiskReasonCode(str, Enum):
    INVALID_RISK_PARAMETER = "INVALID_RISK_PARAMETER"
    INVALID_DISTRIBUTION = "INVALID_DISTRIBUTION"
    INVALID_CORRELATION_MATRIX = "INVALID_CORRELATION_MATRIX"
    NON_POSITIVE_PRICE = "NON_POSITIVE_PRICE"
    NEGATIVE_DURATION = "NEGATIVE_DURATION"
    NO_INPUT_PLAN = "NO_INPUT_PLAN"
    EMPTY_SIMULATION = "EMPTY_SIMULATION"
    SIMULATION_ERROR = "SIMULATION_ERROR"
    INSUFFICIENT_SAMPLES = "INSUFFICIENT_SAMPLES"
    SIMULATION_SUCCESS = "SIMULATION_SUCCESS"


class RiskTier(str, Enum):
    LOW = "LOW"                    # Loss probability < 5%
    MODERATE = "MODERATE"          # Loss probability 5% - 15%
    HIGH = "HIGH"                  # Loss probability 15% - 30%
    CRITICAL = "CRITICAL"          # Loss probability > 30%


class ProvenanceType(str, Enum):
    OBSERVED = "OBSERVED"
    HISTORICAL = "HISTORICAL"
    EMPIRICAL_HISTORICAL = "EMPIRICAL_HISTORICAL"
    FORECAST_RESIDUAL = "FORECAST_RESIDUAL"
    STATISTICAL_MODEL = "STATISTICAL_MODEL"
    SCENARIO_DERIVED = "SCENARIO_DERIVED"
    ASSUMED = "ASSUMED"
    USER_DEFINED = "USER_DEFINED"


class RiskCategory(str, Enum):
    FREIGHT = "FREIGHT"
    BUNKER = "BUNKER"
    SCHEDULE_DELAY = "SCHEDULE_DELAY"
    PORT_DELAY = "PORT_DELAY"
    WEATHER_DELAY = "WEATHER_DELAY"
    PORT_COST = "PORT_COST"
    IDLE_COST = "IDLE_COST"
    OPERATIONAL = "OPERATIONAL"
