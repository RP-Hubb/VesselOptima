"""add_scenario_tables

Revision ID: 8c9d0e1f2a3b
Revises: 7b8c9d0e1f2a
Create Date: 2026-09-06 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c9d0e1f2a3b'
down_revision: Union[str, None] = '7b8c9d0e1f2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create scenario_evaluations table
    op.create_table(
        'scenario_evaluations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('scenario_code', sa.String(length=128), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('scenario_type', sa.String(length=64), nullable=False, server_default='WHAT_IF'),
        sa.Column('baseline_run_id', sa.String(length=128), nullable=False),
        sa.Column('scenario_run_id', sa.String(length=128), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('config_hash', sa.String(length=128), nullable=True),
        sa.Column('comparison_metrics', sa.JSON(), nullable=True),
        sa.Column('assignment_deltas', sa.JSON(), nullable=True),
        sa.Column('cargo_deltas', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('runtime_mode', sa.Enum('LIVE', 'OFFLINE_DEMO', name='runtimemodeenum'), nullable=False),
        sa.Column('audit_trail', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scenario_evaluations_scenario_code', 'scenario_evaluations', ['scenario_code'], unique=False)
    op.create_index('ix_scenario_evaluations_baseline_run_id', 'scenario_evaluations', ['baseline_run_id'], unique=False)
    op.create_index('ix_scenario_evaluations_scenario_run_id', 'scenario_evaluations', ['scenario_run_id'], unique=False)

    # 2. Create scenario_sensitivity_runs table
    op.create_table(
        'scenario_sensitivity_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sweep_id', sa.String(length=128), nullable=False),
        sa.Column('parameter_name', sa.String(length=64), nullable=False),
        sa.Column('baseline_run_id', sa.String(length=128), nullable=False),
        sa.Column('parameter_range', sa.JSON(), nullable=True),
        sa.Column('sweep_points', sa.JSON(), nullable=False),
        sa.Column('break_even_points', sa.JSON(), nullable=True),
        sa.Column('robustness_scores', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('runtime_mode', sa.Enum('LIVE', 'OFFLINE_DEMO', name='runtimemodeenum'), nullable=False),
        sa.Column('audit_trail', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scenario_sensitivity_runs_sweep_id', 'scenario_sensitivity_runs', ['sweep_id'], unique=True)
    op.create_index('ix_scenario_sensitivity_runs_baseline_run_id', 'scenario_sensitivity_runs', ['baseline_run_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_scenario_sensitivity_runs_baseline_run_id', table_name='scenario_sensitivity_runs')
    op.drop_index('ix_scenario_sensitivity_runs_sweep_id', table_name='scenario_sensitivity_runs')
    op.drop_table('scenario_sensitivity_runs')

    op.drop_index('ix_scenario_evaluations_scenario_run_id', table_name='scenario_evaluations')
    op.drop_index('ix_scenario_evaluations_baseline_run_id', table_name='scenario_evaluations')
    op.drop_index('ix_scenario_evaluations_scenario_code', table_name='scenario_evaluations')
    op.drop_table('scenario_evaluations')
