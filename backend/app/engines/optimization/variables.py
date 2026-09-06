"""
VesselOptima — Phase 7: Optimization Decision Variables

Defines structured abstractions for binary assignment variables x_k and cargo slack variables u_c.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class CandidateVariable:
    """Represents the binary decision variable x_k for an admissible Phase 6 candidate."""
    index: int
    candidate_id: str
    vessel_id: int
    vessel_name: str
    cargo_id: Optional[int]
    cargo_name: str
    start_time: datetime
    end_time: datetime
    expected_revenue: float
    voyage_cost: float
    net_contribution: float
    idle_days_saved: float
    avoided_idle_cost: float
    ballast_distance_nm: float
    ballast_days: float
    origin_port_id: Optional[int] = None
    destination_port_id: Optional[int] = None
    employment_type: str = "CARGO_VOYAGE"
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CargoSlackVariable:
    """Represents the binary slack variable u_c for optional cargo rejection."""
    index: int
    cargo_id: int
    cargo_name: str
    unserved_penalty: float = 0.0


@dataclass
class VariableRegistry:
    """Manages the full set of variables in the MILP formulation."""
    candidate_vars: list[CandidateVariable] = field(default_factory=list)
    cargo_slack_vars: list[CargoSlackVariable] = field(default_factory=list)
    candidate_by_id: dict[str, CandidateVariable] = field(default_factory=dict)
    slack_by_cargo_id: dict[int, CargoSlackVariable] = field(default_factory=dict)

    @property
    def total_variables(self) -> int:
        return len(self.candidate_vars) + len(self.cargo_slack_vars)

    @property
    def candidate_count(self) -> int:
        return len(self.candidate_vars)

    @property
    def slack_count(self) -> int:
        return len(self.cargo_slack_vars)

    def add_candidate(self, var: CandidateVariable) -> None:
        self.candidate_vars.append(var)
        self.candidate_by_id[var.candidate_id] = var

    def add_cargo_slack(self, var: CargoSlackVariable) -> None:
        self.cargo_slack_vars.append(var)
        self.slack_by_cargo_id[var.cargo_id] = var

    def get_candidate(self, candidate_id: str) -> Optional[CandidateVariable]:
        return self.candidate_by_id.get(candidate_id)

    def get_cargo_slack(self, cargo_id: int) -> Optional[CargoSlackVariable]:
        return self.slack_by_cargo_id.get(cargo_id)
