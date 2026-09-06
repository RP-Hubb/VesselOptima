"""
VesselOptima — Phase 7: Optimization Constraints Builder

Constructs hard and operational constraints for the MILP formulation:
1. Cargo exclusivity (with optional rejection slack)
2. Vessel exclusivity (interval overlap prevention)
3. Confirmed commitment protection
4. Inter-voyage ballast repositioning & turnaround transition compatibility
5. Vessel availability windows
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from app.engines.optimization.variables import VariableRegistry, CandidateVariable


@dataclass
class LinearConstraintDefinition:
    """Represents a row in the constraint matrix: l_i <= a_i^T x <= u_i"""
    name: str
    constraint_type: str
    coefficients: dict[int, float]  # var_index -> coefficient
    lower_bound: float
    upper_bound: float
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ConstraintBuilder:
    """Builds and audits all constraints for the MILP model."""

    def __init__(self, registry: VariableRegistry, turnaround_hours: float = 24.0):
        self.registry = registry
        self.turnaround_buffer = timedelta(hours=turnaround_hours)
        self.constraints: list[LinearConstraintDefinition] = []
        self.custom_constraints: list[LinearConstraintDefinition] = []

    def add_custom_constraint(self, constraint: LinearConstraintDefinition) -> None:
        """Adds a custom user or scenario constraint."""
        self.custom_constraints.append(constraint)

    def build_all(
        self,
        vessel_commitments: Optional[dict[int, list[tuple[datetime, datetime]]]] = None,
        inter_port_transit_days: Optional[dict[tuple[int, int], float]] = None,
    ) -> list[LinearConstraintDefinition]:
        """Constructs all model constraints."""
        self.constraints.clear()

        # 1. Cargo Exclusivity constraints
        self._build_cargo_exclusivity()

        # 2. Vessel Exclusivity & Overlap constraints
        self._build_vessel_exclusivity()

        # 3. Confirmed Commitment Protection constraints
        if vessel_commitments:
            self._build_commitment_protection(vessel_commitments)

        # 4. Multi-period transition compatibility
        self._build_transition_compatibility(inter_port_transit_days or {})

        # 5. Append any custom constraints
        self.constraints.extend(self.custom_constraints)

        return self.constraints

    def _build_cargo_exclusivity(self) -> None:
        """Each cargo parcel can be served at most once, or left unserved via slack variable."""
        # Group candidate variables by cargo_id
        cargo_to_cands: dict[int, list[CandidateVariable]] = {}
        for c_var in self.registry.candidate_vars:
            if c_var.cargo_id is not None:
                cargo_to_cands.setdefault(c_var.cargo_id, []).append(c_var)

        # Build constraint for each cargo
        for cargo_id, cands in cargo_to_cands.items():
            coeffs: dict[int, float] = {}
            for cand in cands:
                coeffs[cand.index] = 1.0

            slack_var = self.registry.get_cargo_slack(cargo_id)
            if slack_var is not None:
                # With slack: sum(x_k) + u_c = 1.0
                coeffs[slack_var.index] = 1.0
                self.constraints.append(
                    LinearConstraintDefinition(
                        name=f"cargo_exclusivity_exact_{cargo_id}",
                        constraint_type="CARGO_EXCLUSIVITY",
                        coefficients=coeffs,
                        lower_bound=1.0,
                        upper_bound=1.0,
                        description=f"Cargo {cargo_id} must be served by at most one vessel or flagged unserved.",
                        metadata={"cargo_id": cargo_id, "candidates": [c.candidate_id for c in cands]},
                    )
                )
            else:
                # Without slack: sum(x_k) <= 1.0
                self.constraints.append(
                    LinearConstraintDefinition(
                        name=f"cargo_exclusivity_le_{cargo_id}",
                        constraint_type="CARGO_EXCLUSIVITY",
                        coefficients=coeffs,
                        lower_bound=0.0,
                        upper_bound=1.0,
                        description=f"Cargo {cargo_id} can be assigned to at most one vessel.",
                        metadata={"cargo_id": cargo_id, "candidates": [c.candidate_id for c in cands]},
                    )
                )

    def _build_vessel_exclusivity(self) -> None:
        """A vessel cannot perform multiple overlapping voyages."""
        # Group candidates by vessel_id
        vessel_to_cands: dict[int, list[CandidateVariable]] = {}
        for c_var in self.registry.candidate_vars:
            vessel_to_cands.setdefault(c_var.vessel_id, []).append(c_var)

        for vessel_id, cands in vessel_to_cands.items():
            n = len(cands)
            for i in range(n):
                for j in range(i + 1, n):
                    cand_a = cands[i]
                    cand_b = cands[j]

                    # Check interval overlap (with turnaround buffer)
                    # Overlap occurs if max(S_a, S_b) < min(E_a, E_b)
                    start_a = cand_a.start_time
                    end_a = cand_a.end_time + self.turnaround_buffer
                    start_b = cand_b.start_time
                    end_b = cand_b.end_time + self.turnaround_buffer

                    if max(start_a, start_b) < min(end_a, end_b):
                        # Overlapping: x_a + x_b <= 1
                        self.constraints.append(
                            LinearConstraintDefinition(
                                name=f"vessel_overlap_{vessel_id}_{cand_a.index}_{cand_b.index}",
                                constraint_type="VESSEL_EXCLUSIVITY",
                                coefficients={cand_a.index: 1.0, cand_b.index: 1.0},
                                lower_bound=0.0,
                                upper_bound=1.0,
                                description=f"Vessel {vessel_id} cannot simultaneously perform overlapping candidates {cand_a.candidate_id} and {cand_b.candidate_id}.",
                                metadata={
                                    "vessel_id": vessel_id,
                                    "candidate_a": cand_a.candidate_id,
                                    "candidate_b": cand_b.candidate_id,
                                },
                            )
                        )

    def _build_commitment_protection(
        self, commitments: dict[int, list[tuple[datetime, datetime]]]
    ) -> None:
        """Any candidate overlapping with an existing confirmed commitment fixture must be excluded (x_k = 0)."""
        for c_var in self.registry.candidate_vars:
            v_commitments = commitments.get(c_var.vessel_id, [])
            c_start = c_var.start_time
            c_end = c_var.end_time + self.turnaround_buffer

            for comm_start, comm_end in v_commitments:
                if max(c_start, comm_start) < min(c_end, comm_end):
                    # Hard constraint: x_k == 0
                    self.constraints.append(
                        LinearConstraintDefinition(
                            name=f"commitment_protection_{c_var.vessel_id}_{c_var.index}",
                            constraint_type="COMMITMENT_PROTECTION",
                            coefficients={c_var.index: 1.0},
                            lower_bound=0.0,
                            upper_bound=0.0,
                            description=f"Candidate {c_var.candidate_id} conflicts with confirmed commitment on vessel {c_var.vessel_id}.",
                            metadata={
                                "candidate_id": c_var.candidate_id,
                                "vessel_id": c_var.vessel_id,
                                "commitment_window": [comm_start.isoformat(), comm_end.isoformat()],
                            },
                        )
                    )
                    break

    def _build_transition_compatibility(
        self, inter_port_transit_days: dict[tuple[int, int], float]
    ) -> None:
        """For sequential candidates on the same vessel, ensure sufficient ballast repositioning days between voyages."""
        vessel_to_cands: dict[int, list[CandidateVariable]] = {}
        for c_var in self.registry.candidate_vars:
            vessel_to_cands.setdefault(c_var.vessel_id, []).append(c_var)

        for vessel_id, cands in vessel_to_cands.items():
            # Sort by start_time
            sorted_cands = sorted(cands, key=lambda c: c.start_time)
            n = len(sorted_cands)
            for i in range(n):
                for j in range(i + 1, n):
                    cand_first = sorted_cands[i]
                    cand_second = sorted_cands[j]

                    # If they already overlap, vessel_exclusivity covers it
                    if cand_first.end_time >= cand_second.start_time:
                        continue

                    # Check transition from dest(cand_first) to orig(cand_second)
                    dest_port = cand_first.destination_port_id
                    orig_port = cand_second.origin_port_id

                    required_ballast_days = 0.0
                    if dest_port is not None and orig_port is not None:
                        if dest_port != orig_port:
                            required_ballast_days = inter_port_transit_days.get((dest_port, orig_port), 2.0)

                    min_required_gap = timedelta(days=required_ballast_days) + self.turnaround_buffer
                    available_gap = cand_second.start_time - cand_first.end_time

                    if available_gap < min_required_gap:
                        # Incompatible transition: x_first + x_second <= 1
                        self.constraints.append(
                            LinearConstraintDefinition(
                                name=f"transition_incompatible_{vessel_id}_{cand_first.index}_{cand_second.index}",
                                constraint_type="TRANSITION_TIMING",
                                coefficients={cand_first.index: 1.0, cand_second.index: 1.0},
                                lower_bound=0.0,
                                upper_bound=1.0,
                                description=(
                                    f"Insufficient ballast time ({available_gap.total_seconds() / 86400:.1f}d available vs "
                                    f"{min_required_gap.total_seconds() / 86400:.1f}d required) between {cand_first.candidate_id} "
                                    f"and {cand_second.candidate_id} on vessel {vessel_id}."
                                ),
                                metadata={
                                    "vessel_id": vessel_id,
                                    "first_candidate": cand_first.candidate_id,
                                    "second_candidate": cand_second.candidate_id,
                                    "available_days": available_gap.total_seconds() / 86400,
                                    "required_days": min_required_gap.total_seconds() / 86400,
                                },
                            )
                        )
