"""
VesselOptima — Phase 7: Optimization Objective Builder

Constructs the linear objective coefficients and provides mathematical decomposition
into explicit, auditable USD economic components:
1. Gross freight revenue
2. Direct voyage operating & fuel expenses
3. Net voyage economic contribution
4. Avoided idle holding costs
5. Ballast positioning penalties
6. Unserved cargo slack penalties
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.engines.optimization.variables import VariableRegistry


@dataclass
class ObjectiveConfig:
    """Configurable weights and penalties for the MILP objective."""
    alpha_idle_weight: float = 1.0          # Multiplier for avoided idle holding costs (0.0 to 1.0)
    beta_ballast_penalty: float = 0.0       # Direct penalty rate per ballast day or nm ($/day)
    default_unserved_penalty: float = 0.0   # Penalty for leaving optional cargo unserved ($)
    cargo_penalties: dict[int, float] = field(default_factory=dict)  # cargo_id -> penalty ($)


@dataclass
class ObjectiveDecomposition:
    """Explicit, auditable unit-consistent (USD) decomposition of the optimized fleet objective."""
    total_gross_revenue: float = 0.0
    total_voyage_cost: float = 0.0
    total_net_contribution: float = 0.0
    total_avoided_idle_cost: float = 0.0
    total_ballast_penalty: float = 0.0
    total_unserved_penalty: float = 0.0
    global_objective_value: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "total_gross_revenue": round(self.total_gross_revenue, 2),
            "total_voyage_cost": round(self.total_voyage_cost, 2),
            "total_net_contribution": round(self.total_net_contribution, 2),
            "total_avoided_idle_cost": round(self.total_avoided_idle_cost, 2),
            "total_ballast_penalty": round(self.total_ballast_penalty, 2),
            "total_unserved_penalty": round(self.total_unserved_penalty, 2),
            "global_objective_value": round(self.global_objective_value, 2),
        }


class ObjectiveBuilder:
    """Builds minimization cost vector c for the solver and computes objective decompositions."""

    def __init__(self, registry: VariableRegistry, config: ObjectiveConfig | None = None):
        self.registry = registry
        self.config = config or ObjectiveConfig()

    def build_cost_vector(self) -> list[float]:
        """
        Builds the cost vector c for standard minimization: min c^T x.
        Since we want to MAXIMIZE:
            Z = sum_k (P_k + alpha * I_k - beta * B_k) * x_k - sum_c gamma_c * u_c
        Minimizing -Z means:
            c_k = -(P_k + alpha * I_k - beta * B_k)
            c_c = +gamma_c
        """
        c_vector: list[float] = [0.0] * self.registry.total_variables

        # Candidate variables
        for c_var in self.registry.candidate_vars:
            # P_k: Net voyage contribution (from Phase 6 economics)
            p_k = c_var.net_contribution
            # I_k: Avoided idle holding cost
            i_k = c_var.avoided_idle_cost
            # B_k: Ballast penalty
            b_k = self.config.beta_ballast_penalty * c_var.ballast_days

            effective_reward = p_k + (self.config.alpha_idle_weight * i_k) - b_k
            # Minimization coefficient is negative of reward
            c_vector[c_var.index] = -effective_reward

        # Cargo slack variables
        for s_var in self.registry.cargo_slack_vars:
            penalty = self.config.cargo_penalties.get(s_var.cargo_id, self.config.default_unserved_penalty)
            s_var.unserved_penalty = penalty
            # Positive cost if cargo is left unserved
            c_vector[s_var.index] = penalty

        return c_vector

    def decompose_solution(self, solution_values: list[float]) -> ObjectiveDecomposition:
        """Decomposes the primal binary solution into explicit economic USD components."""
        decomp = ObjectiveDecomposition()

        for c_var in self.registry.candidate_vars:
            val = solution_values[c_var.index] if c_var.index < len(solution_values) else 0.0
            if val > 0.5:  # Variable selected (x_k = 1)
                decomp.total_gross_revenue += c_var.expected_revenue
                decomp.total_voyage_cost += c_var.voyage_cost
                decomp.total_net_contribution += c_var.net_contribution
                decomp.total_avoided_idle_cost += (self.config.alpha_idle_weight * c_var.avoided_idle_cost)
                decomp.total_ballast_penalty += (self.config.beta_ballast_penalty * c_var.ballast_days)

        for s_var in self.registry.cargo_slack_vars:
            val = solution_values[s_var.index] if s_var.index < len(solution_values) else 0.0
            if val > 0.5:  # Cargo left unserved (u_c = 1)
                decomp.total_unserved_penalty += s_var.unserved_penalty

        decomp.global_objective_value = (
            decomp.total_net_contribution
            + decomp.total_avoided_idle_cost
            - decomp.total_ballast_penalty
            - decomp.total_unserved_penalty
        )

        return decomp
