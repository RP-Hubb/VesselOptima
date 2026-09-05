"""add_procurement_tables

Revision ID: 5f6a7b8c9d0e
Revises: 4e5f6a7b8c9d
Create Date: 2026-09-05 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f6a7b8c9d0e'
down_revision: Union[str, None] = '4e5f6a7b8c9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('procurement_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('profile_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('tender_preparation_days', sa.Float(), nullable=False),
        sa.Column('bid_submission_days', sa.Float(), nullable=False),
        sa.Column('technical_evaluation_days', sa.Float(), nullable=False),
        sa.Column('commercial_evaluation_days', sa.Float(), nullable=False),
        sa.Column('approval_days', sa.Float(), nullable=False),
        sa.Column('award_days', sa.Float(), nullable=False),
        sa.Column('minimum_lead_time_days', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('data_classification', sa.String(length=64), nullable=False),
        sa.Column('provenance', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profile_id')
    )
    op.create_index('ix_procurement_configs_profile_id', 'procurement_configs', ['profile_id'], unique=True)

    op.create_table('procurement_evaluations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cargo_id', sa.Integer(), nullable=True),
        sa.Column('profile_id', sa.String(length=64), nullable=False),
        sa.Column('strategy_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('timing_signal', sa.String(length=64), nullable=False),
        sa.Column('candidate_data', sa.JSON(), nullable=True),
        sa.Column('timing_detail', sa.JSON(), nullable=True),
        sa.Column('cost_detail', sa.JSON(), nullable=True),
        sa.Column('forecast_detail', sa.JSON(), nullable=True),
        sa.Column('feasibility_detail', sa.JSON(), nullable=True),
        sa.Column('assumptions', sa.JSON(), nullable=True),
        sa.Column('provenance', sa.JSON(), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(), nullable=False),
        sa.Column('runtime_mode', sa.Enum('LIVE', 'OFFLINE_DEMO', name='runtimemodeenum'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['cargo_id'], ['cargo_parcels.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_procurement_evaluations_cargo_id', 'procurement_evaluations', ['cargo_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_procurement_evaluations_cargo_id', table_name='procurement_evaluations')
    op.drop_table('procurement_evaluations')
    op.drop_index('ix_procurement_configs_profile_id', table_name='procurement_configs')
    op.drop_table('procurement_configs')
