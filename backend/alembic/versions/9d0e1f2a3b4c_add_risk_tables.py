"""add_risk_tables

Revision ID: 9d0e1f2a3b4c
Revises: 8c9d0e1f2a3b
Create Date: 2026-09-06 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d0e1f2a3b4c'
down_revision: Union[str, None] = '8c9d0e1f2a3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create risk_runs table
    op.create_table(
        'risk_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.String(length=128), nullable=False),
        sa.Column('optimization_run_id', sa.String(length=128), nullable=False),
        sa.Column('scenario_run_id', sa.String(length=128), nullable=True),
        sa.Column('simulation_count', sa.Integer(), nullable=False, server_default='5000'),
        sa.Column('random_seed', sa.Integer(), nullable=False, server_default='42'),
        sa.Column('simulation_parameters', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='COMPLETED'),
        sa.Column('execution_time_seconds', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('audit_trail', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('runtime_mode', sa.Enum('LIVE', 'OFFLINE_DEMO', name='runtimemodeenum'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_risk_runs_run_id', 'risk_runs', ['run_id'], unique=True)
    op.create_index('ix_risk_runs_optimization_run_id', 'risk_runs', ['optimization_run_id'], unique=False)
    op.create_index('ix_risk_runs_scenario_run_id', 'risk_runs', ['scenario_run_id'], unique=False)

    # 2. Create risk_metrics table
    op.create_table(
        'risk_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('risk_run_id', sa.Integer(), nullable=False),
        sa.Column('expected_contribution', sa.Float(), nullable=False),
        sa.Column('contribution_std', sa.Float(), nullable=False),
        sa.Column('percentiles', sa.JSON(), nullable=False),
        sa.Column('var90', sa.Float(), nullable=False),
        sa.Column('var95', sa.Float(), nullable=False),
        sa.Column('var95_downside', sa.Float(), nullable=False),
        sa.Column('cvar90', sa.Float(), nullable=False),
        sa.Column('cvar95', sa.Float(), nullable=False),
        sa.Column('loss_probability', sa.Float(), nullable=False),
        sa.Column('expected_loss', sa.Float(), nullable=False),
        sa.Column('plan_reliability_score', sa.Float(), nullable=False),
        sa.Column('risk_tier', sa.String(length=32), nullable=False, server_default='MODERATE'),
        sa.Column('distribution_summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['risk_run_id'], ['risk_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_risk_metrics_risk_run_id', 'risk_metrics', ['risk_run_id'], unique=True)

    # 3. Create risk_assignment_metrics table
    op.create_table(
        'risk_assignment_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('risk_run_id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.String(length=128), nullable=False),
        sa.Column('vessel_id', sa.Integer(), nullable=False),
        sa.Column('cargo_id', sa.Integer(), nullable=True),
        sa.Column('expected_net_contribution', sa.Float(), nullable=False),
        sa.Column('contribution_std', sa.Float(), nullable=False),
        sa.Column('loss_probability', sa.Float(), nullable=False),
        sa.Column('cvar95', sa.Float(), nullable=False),
        sa.Column('expected_arrival', sa.DateTime(), nullable=True),
        sa.Column('p90_arrival', sa.DateTime(), nullable=True),
        sa.Column('schedule_buffer_days', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('laycan_miss_probability', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('economic_survival_probability', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('schedule_survival_probability', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('risk_tier', sa.String(length=32), nullable=False, server_default='MODERATE'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['risk_run_id'], ['risk_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vessel_id'], ['vessel_profiles.id']),
        sa.ForeignKeyConstraint(['cargo_id'], ['cargo_parcels.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_risk_assignment_metrics_risk_run_id', 'risk_assignment_metrics', ['risk_run_id'], unique=False)
    op.create_index('ix_risk_assignment_metrics_candidate_id', 'risk_assignment_metrics', ['candidate_id'], unique=False)

    # 4. Create risk_drivers table
    op.create_table(
        'risk_drivers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('risk_run_id', sa.Integer(), nullable=False),
        sa.Column('variable_id', sa.String(length=64), nullable=False),
        sa.Column('variable_name', sa.String(length=128), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('uncertainty_contribution_pct', sa.Float(), nullable=False),
        sa.Column('sensitivity_coefficient', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['risk_run_id'], ['risk_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_risk_drivers_risk_run_id', 'risk_drivers', ['risk_run_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_risk_drivers_risk_run_id', table_name='risk_drivers')
    op.drop_table('risk_drivers')

    op.drop_index('ix_risk_assignment_metrics_candidate_id', table_name='risk_assignment_metrics')
    op.drop_index('ix_risk_assignment_metrics_risk_run_id', table_name='risk_assignment_metrics')
    op.drop_table('risk_assignment_metrics')

    op.drop_index('ix_risk_metrics_risk_run_id', table_name='risk_metrics')
    op.drop_table('risk_metrics')

    op.drop_index('ix_risk_runs_scenario_run_id', table_name='risk_runs')
    op.drop_index('ix_risk_runs_optimization_run_id', table_name='risk_runs')
    op.drop_index('ix_risk_runs_run_id', table_name='risk_runs')
    op.drop_table('risk_runs')
