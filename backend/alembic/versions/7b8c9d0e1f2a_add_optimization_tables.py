"""add_optimization_tables

Revision ID: 7b8c9d0e1f2a
Revises: 6a7b8c9d0e1f
Create Date: 2026-09-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b8c9d0e1f2a'
down_revision: Union[str, None] = '6a7b8c9d0e1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update optimization_runs table with Phase 7 columns
    with op.batch_alter_table('optimization_runs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('run_id', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('total_revenue', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('total_cost', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('total_contribution', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('avoided_idle_cost', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('solver_name', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('solver_status', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('objective_decomposition', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('solver_metadata', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('audit_trail', sa.JSON(), nullable=True))
        batch_op.create_index('ix_optimization_runs_run_id', ['run_id'], unique=True)

    # 2. Create optimization_assignments table
    op.create_table(
        'optimization_assignments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('optimization_run_id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.String(length=128), nullable=False),
        sa.Column('vessel_id', sa.Integer(), nullable=False),
        sa.Column('cargo_id', sa.Integer(), nullable=True),
        sa.Column('is_selected', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('selection_status', sa.String(length=64), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('expected_revenue', sa.Float(), nullable=True),
        sa.Column('voyage_cost', sa.Float(), nullable=True),
        sa.Column('gross_contribution', sa.Float(), nullable=True),
        sa.Column('ballast_distance_nm', sa.Float(), nullable=True),
        sa.Column('ballast_days', sa.Float(), nullable=True),
        sa.Column('voyage_days', sa.Float(), nullable=True),
        sa.Column('assignment_metadata', sa.JSON(), nullable=True),
        sa.Column('trade_off_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('runtime_mode', sa.Enum('LIVE', 'OFFLINE_DEMO', name='runtimemodeenum'), nullable=False),
        sa.ForeignKeyConstraint(['cargo_id'], ['cargo_parcels.id'], ),
        sa.ForeignKeyConstraint(['optimization_run_id'], ['optimization_runs.id'], ),
        sa.ForeignKeyConstraint(['vessel_id'], ['vessel_profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_optimization_assignments_candidate_id', 'optimization_assignments', ['candidate_id'], unique=False)
    op.create_index('ix_optimization_assignments_cargo_id', 'optimization_assignments', ['cargo_id'], unique=False)
    op.create_index('ix_optimization_assignments_optimization_run_id', 'optimization_assignments', ['optimization_run_id'], unique=False)
    op.create_index('ix_optimization_assignments_vessel_id', 'optimization_assignments', ['vessel_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_optimization_assignments_vessel_id', table_name='optimization_assignments')
    op.drop_index('ix_optimization_assignments_optimization_run_id', table_name='optimization_assignments')
    op.drop_index('ix_optimization_assignments_cargo_id', table_name='optimization_assignments')
    op.drop_index('ix_optimization_assignments_candidate_id', table_name='optimization_assignments')
    op.drop_table('optimization_assignments')

    with op.batch_alter_table('optimization_runs', schema=None) as batch_op:
        batch_op.drop_index('ix_optimization_runs_run_id')
        batch_op.drop_column('audit_trail')
        batch_op.drop_column('solver_metadata')
        batch_op.drop_column('objective_decomposition')
        batch_op.drop_column('solver_status')
        batch_op.drop_column('solver_name')
        batch_op.drop_column('avoided_idle_cost')
        batch_op.drop_column('total_contribution')
        batch_op.drop_column('total_cost')
        batch_op.drop_column('total_revenue')
        batch_op.drop_column('run_id')
