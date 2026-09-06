"""
VesselOptima — Phase 9: Risk Data Models & Configuration

Formal configuration models for risk variables, stochastic distributions,
correlation structures, and Monte Carlo simulation settings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.engines.risk.reason_codes import ProvenanceType, RiskCategory


class DistributionType(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    NORMAL = "NORMAL"
    LOGNORMAL = "LOGNORMAL"
    TRIANGULAR = "TRIANGULAR"
    UNIFORM = "UNIFORM"
    EMPIRICAL = "EMPIRICAL"


@dataclass
class RiskVariable:
    """
    Specification of an uncertain parameter in the voyage economic/operational system.
    """
    variable_id: str
    name: str
    category: RiskCategory
    distribution_type: DistributionType
    parameters: Dict[str, Any]
    baseline_value: Optional[float] = None
    unit: str = "USD"
    source: str = "CANONICAL_INDEX"
    source_ref: Optional[str] = None
    provenance_type: ProvenanceType = ProvenanceType.ASSUMED
    provenance: Optional[ProvenanceType] = None
    correlation_group: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.provenance is not None:
            self.provenance_type = self.provenance
        elif self.provenance_type is not None:
            self.provenance = self.provenance_type
        if self.source_ref is not None:
            self.source = self.source_ref

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value if isinstance(self.category, RiskCategory) else str(self.category)
        d["distribution_type"] = (
            self.distribution_type.value if isinstance(self.distribution_type, DistributionType) else str(self.distribution_type)
        )
        d["provenance_type"] = (
            self.provenance_type.value if isinstance(self.provenance_type, ProvenanceType) else str(self.provenance_type)
        )
        d["provenance"] = d["provenance_type"]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RiskVariable:
        cat = RiskCategory(data["category"]) if isinstance(data.get("category"), str) else data["category"]
        dtype = DistributionType(data["distribution_type"]) if isinstance(data.get("distribution_type"), str) else data["distribution_type"]
        prov_val = data.get("provenance", data.get("provenance_type", "ASSUMED"))
        prov = ProvenanceType(prov_val) if isinstance(prov_val, str) else prov_val
        return cls(
            variable_id=data["variable_id"],
            name=data["name"],
            category=cat,
            distribution_type=dtype,
            parameters=data.get("parameters", {}),
            baseline_value=data.get("baseline_value"),
            unit=data.get("unit", "USD"),
            source=data.get("source", "CANONICAL_INDEX"),
            source_ref=data.get("source_ref"),
            provenance_type=prov,
            provenance=prov,
            correlation_group=data.get("correlation_group"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CorrelationConfig:
    """
    Correlation matrix configuration for a group of risk variables.
    """
    variable_ids: List[str]
    matrix: List[List[float]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CorrelationConfig:
        return cls(
            variable_ids=data["variable_ids"],
            matrix=data["matrix"],
        )


@dataclass
class RiskSimulationConfig:
    """
    Configuration parameters for a Monte Carlo simulation execution.
    """
    simulation_count: int = 5000
    random_seed: int = 42
    variables: List[RiskVariable] = field(default_factory=list)
    correlation_config: Optional[CorrelationConfig] = None
    correlations: List[CorrelationConfig] = field(default_factory=list)
    loss_threshold: float = 0.0
    var_confidence_levels: List[float] = field(default_factory=lambda: [0.90, 0.95])
    confidence_levels: List[float] = field(default_factory=lambda: [0.90, 0.95])
    risk_tier_thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "low": 0.05,        # < 5%
            "moderate": 0.15,   # 5% - 15%
            "high": 0.30,       # 15% - 30%
        }
    )
    include_demurrage: bool = True
    demurrage_daily_rate: float = 15000.0
    idle_daily_holding_cost: float = 8500.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.correlation_config is not None and not self.correlations:
            self.correlations = [self.correlation_config]
        elif self.correlations and self.correlation_config is None:
            self.correlation_config = self.correlations[0]
        if self.confidence_levels and not self.var_confidence_levels:
            self.var_confidence_levels = self.confidence_levels
        elif self.var_confidence_levels and not self.confidence_levels:
            self.confidence_levels = self.var_confidence_levels

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_count": self.simulation_count,
            "random_seed": self.random_seed,
            "variables": [v.to_dict() for v in self.variables],
            "correlation_config": self.correlation_config.to_dict() if self.correlation_config else None,
            "correlations": [c.to_dict() for c in self.correlations],
            "loss_threshold": self.loss_threshold,
            "var_confidence_levels": self.var_confidence_levels,
            "confidence_levels": self.confidence_levels,
            "risk_tier_thresholds": self.risk_tier_thresholds,
            "include_demurrage": self.include_demurrage,
            "demurrage_daily_rate": self.demurrage_daily_rate,
            "idle_daily_holding_cost": self.idle_daily_holding_cost,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RiskSimulationConfig:
        corr = CorrelationConfig.from_dict(data["correlation_config"]) if data.get("correlation_config") else None
        corrs = [CorrelationConfig.from_dict(c) for c in data.get("correlations", [])]
        if corr and not corrs:
            corrs = [corr]
        vars_list = [RiskVariable.from_dict(v) for v in data.get("variables", [])]
        return cls(
            simulation_count=int(data.get("simulation_count", 5000)),
            random_seed=int(data.get("random_seed", 42)),
            variables=vars_list,
            correlation_config=corr,
            correlations=corrs,
            loss_threshold=float(data.get("loss_threshold", 0.0)),
            var_confidence_levels=[float(c) for c in data.get("var_confidence_levels", [0.90, 0.95])],
            confidence_levels=[float(c) for c in data.get("confidence_levels", [0.90, 0.95])],
            risk_tier_thresholds=data.get("risk_tier_thresholds", {"low": 0.05, "moderate": 0.15, "high": 0.30}),
            include_demurrage=bool(data.get("include_demurrage", True)),
            demurrage_daily_rate=float(data.get("demurrage_daily_rate", 15000.0)),
            idle_daily_holding_cost=float(data.get("idle_daily_holding_cost", 8500.0)),
            metadata=data.get("metadata", {}),
        )
