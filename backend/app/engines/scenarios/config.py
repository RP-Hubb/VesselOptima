"""
VesselOptima — Phase 8: Scenario Configuration & Presets

Defines the formal configuration model for scenario experimentation,
parameter adjustments, and institutional presets.
Strictly adheres to baseline immutability and copy-on-scenario semantics.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ScenarioType(str, Enum):
    BASELINE = "BASELINE"
    FREIGHT = "FREIGHT"
    BUNKER = "BUNKER"
    IDLE_COST = "IDLE_COST"
    PORT_COST = "PORT_COST"
    LAYCAN = "LAYCAN"
    FLEET_AVAILABILITY = "FLEET_AVAILABILITY"
    MARKET_STRESS = "MARKET_STRESS"
    CUSTOM = "CUSTOM"


@dataclass
class ScenarioConfig:
    """
    Formal configuration parameters for a what-if scenario.
    All multipliers default to 1.0 (no change / baseline equivalence).
    """
    scenario_id: str
    name: str
    description: str = ""
    scenario_type: ScenarioType = ScenarioType.CUSTOM
    base_run_id: Optional[str] = None
    baseline_scenario: str = "DEMO_FLEET"

    # Economic Multipliers
    freight_multiplier: float = 1.0
    bunker_multiplier: float = 1.0
    idle_cost_multiplier: float = 1.0
    port_cost_multiplier: float = 1.0

    # Operational Adjustments
    laycan_adjustment_days: float = 0.0  # Positive tightening (e.g. 2.0 = window ends 2 days earlier)
    excluded_vessel_ids: List[int] = field(default_factory=list)
    vessel_delay_days: Dict[int, float] = field(default_factory=dict)  # vessel_id -> days delayed

    # Objective weights for Phase 7 MILP
    alpha_idle_weight: float = 1.0
    beta_ballast_penalty: float = 0.0
    default_unserved_penalty: float = 0.0

    # Metadata & Provenance
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scenario_type"] = self.scenario_type.value if isinstance(self.scenario_type, ScenarioType) else str(self.scenario_type)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScenarioConfig:
        raw_type = data.get("scenario_type", "CUSTOM")
        try:
            stype = ScenarioType(raw_type)
        except ValueError:
            stype = ScenarioType.CUSTOM

        return cls(
            scenario_id=data.get("scenario_id", "SCEN-CUSTOM"),
            name=data.get("name", "Custom Scenario"),
            description=data.get("description", ""),
            scenario_type=stype,
            base_run_id=data.get("base_run_id"),
            baseline_scenario=data.get("baseline_scenario", "DEMO_FLEET"),
            freight_multiplier=float(data.get("freight_multiplier", 1.0)),
            bunker_multiplier=float(data.get("bunker_multiplier", 1.0)),
            idle_cost_multiplier=float(data.get("idle_cost_multiplier", 1.0)),
            port_cost_multiplier=float(data.get("port_cost_multiplier", 1.0)),
            laycan_adjustment_days=float(data.get("laycan_adjustment_days", 0.0)),
            excluded_vessel_ids=[int(v) for v in data.get("excluded_vessel_ids", [])],
            vessel_delay_days={int(k): float(v) for k, v in data.get("vessel_delay_days", {}).items()},
            alpha_idle_weight=float(data.get("alpha_idle_weight", 1.0)),
            beta_ballast_penalty=float(data.get("beta_ballast_penalty", 0.0)),
            default_unserved_penalty=float(data.get("default_unserved_penalty", 0.0)),
            metadata=data.get("metadata", {}),
        )

    def get_config_hash(self) -> str:
        """Computes a deterministic SHA-256 hash of this configuration."""
        canonical_payload = {
            "scenario_id": self.scenario_id,
            "baseline_scenario": self.baseline_scenario,
            "freight_multiplier": round(self.freight_multiplier, 4),
            "bunker_multiplier": round(self.bunker_multiplier, 4),
            "idle_cost_multiplier": round(self.idle_cost_multiplier, 4),
            "port_cost_multiplier": round(self.port_cost_multiplier, 4),
            "laycan_adjustment_days": round(self.laycan_adjustment_days, 2),
            "excluded_vessel_ids": sorted(self.excluded_vessel_ids),
            "vessel_delay_days": {str(k): round(v, 2) for k, v in sorted(self.vessel_delay_days.items())},
            "alpha_idle_weight": round(self.alpha_idle_weight, 4),
            "beta_ballast_penalty": round(self.beta_ballast_penalty, 4),
            "default_unserved_penalty": round(self.default_unserved_penalty, 4),
        }
        encoded = json.dumps(canonical_payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ScenarioPresets:
    """Standard institutional preset scenarios for what-if stress testing."""

    @staticmethod
    def baseline(scenario_id: str = "SCEN-BASE", baseline_scenario: str = "DEMO_FLEET") -> ScenarioConfig:
        return ScenarioConfig(
            scenario_id=scenario_id,
            name="Baseline Fleet Plan",
            description="Reference baseline allocation with default market rates, bunker costs, and schedules.",
            scenario_type=ScenarioType.BASELINE,
            baseline_scenario=baseline_scenario,
        )

    @staticmethod
    def bunker_plus_25(scenario_id: str = "SCEN-BUNKER-25", baseline_scenario: str = "DEMO_FLEET") -> ScenarioConfig:
        return ScenarioConfig(
            scenario_id=scenario_id,
            name="Bunker Price Surge (+25%)",
            description="Simulates a 25% increase in VLSFO/LSMGO bunker fuel prices across all trade routes.",
            scenario_type=ScenarioType.BUNKER,
            baseline_scenario=baseline_scenario,
            bunker_multiplier=1.25,
        )

    @staticmethod
    def bunker_plus_50(scenario_id: str = "SCEN-BUNKER-50", baseline_scenario: str = "DEMO_FLEET") -> ScenarioConfig:
        return ScenarioConfig(
            scenario_id=scenario_id,
            name="Bunker Price Shock (+50%)",
            description="Extreme bunker price shock (+50%) testing the economic viability of long-ballast voyages.",
            scenario_type=ScenarioType.BUNKER,
            baseline_scenario=baseline_scenario,
            bunker_multiplier=1.50,
        )

    @staticmethod
    def freight_minus_10(scenario_id: str = "SCEN-FREIGHT-M10", baseline_scenario: str = "DEMO_FLEET") -> ScenarioConfig:
        return ScenarioConfig(
            scenario_id=scenario_id,
            name="Freight Rate Softening (-10%)",
            description="Market downturn softening gross freight spot revenues by 10%.",
            scenario_type=ScenarioType.FREIGHT,
            baseline_scenario=baseline_scenario,
            freight_multiplier=0.90,
        )

    @staticmethod
    def freight_minus_20(scenario_id: str = "SCEN-FREIGHT-M20", baseline_scenario: str = "DEMO_FLEET") -> ScenarioConfig:
        return ScenarioConfig(
            scenario_id=scenario_id,
            name="Freight Rate Slump (-20%)",
            description="Severe market contraction testing marginal cargo acceptance and trade-off rejections.",
            scenario_type=ScenarioType.FREIGHT,
            baseline_scenario=baseline_scenario,
            freight_multiplier=0.80,
        )

    @staticmethod
    def freight_plus_20(scenario_id: str = "SCEN-FREIGHT-P20", baseline_scenario: str = "DEMO_FLEET") -> ScenarioConfig:
        return ScenarioConfig(
            scenario_id=scenario_id,
            name="Freight Rate Bull Market (+20%)",
            description="Bullish freight market expanding gross freight revenues by 20%.",
            scenario_type=ScenarioType.FREIGHT,
            baseline_scenario=baseline_scenario,
            freight_multiplier=1.20,
        )

    @staticmethod
    def idle_plus_50(scenario_id: str = "SCEN-IDLE-P50", baseline_scenario: str = "DEMO_FLEET") -> ScenarioConfig:
        return ScenarioConfig(
            scenario_id=scenario_id,
            name="Idle Cost Penalty Escalation (+50%)",
            description="Daily idle holding and lay-up penalties increase by 50%, heavily penalizing unassigned fleet days.",
            scenario_type=ScenarioType.IDLE_COST,
            baseline_scenario=baseline_scenario,
            idle_cost_multiplier=1.50,
        )

    @staticmethod
    def market_stress(scenario_id: str = "SCEN-STRESS", baseline_scenario: str = "DEMO_FLEET") -> ScenarioConfig:
        return ScenarioConfig(
            scenario_id=scenario_id,
            name="Freight Market Multi-Stress",
            description="Compound macro stress test: Freight -20%, Bunker +30%, and Idle Cost +20%.",
            scenario_type=ScenarioType.MARKET_STRESS,
            baseline_scenario=baseline_scenario,
            freight_multiplier=0.80,
            bunker_multiplier=1.30,
            idle_cost_multiplier=1.20,
        )

    @staticmethod
    def tight_laycan(scenario_id: str = "SCEN-TIGHT-LAYCAN", baseline_scenario: str = "DEMO_FLEET", days: float = 3.0) -> ScenarioConfig:
        return ScenarioConfig(
            scenario_id=scenario_id,
            name=f"Tightened Laycan Windows (-{days:.0f} Days)",
            description=f"Shrinks cargo arrival laycan windows by {days:.0f} days, re-validating physical presentation feasibility.",
            scenario_type=ScenarioType.LAYCAN,
            baseline_scenario=baseline_scenario,
            laycan_adjustment_days=days,
        )

    @staticmethod
    def vessel_outage(scenario_id: str = "SCEN-OUTAGE", baseline_scenario: str = "DEMO_FLEET", excluded_id: int = 1) -> ScenarioConfig:
        return ScenarioConfig(
            scenario_id=scenario_id,
            name=f"Vessel Outage (Vessel {excluded_id})",
            description=f"Simulates unscheduled drydock / engine casualty rendering Vessel {excluded_id} unavailable.",
            scenario_type=ScenarioType.FLEET_AVAILABILITY,
            baseline_scenario=baseline_scenario,
            excluded_vessel_ids=[excluded_id],
        )

    @classmethod
    def all_presets(cls) -> List[ScenarioConfig]:
        return [
            cls.baseline(),
            cls.bunker_plus_25(),
            cls.bunker_plus_50(),
            cls.freight_minus_10(),
            cls.freight_minus_20(),
            cls.freight_plus_20(),
            cls.idle_plus_50(),
            cls.market_stress(),
            cls.tight_laycan(),
            cls.vessel_outage(),
        ]
