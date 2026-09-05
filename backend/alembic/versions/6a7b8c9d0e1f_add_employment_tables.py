"""add_employment_tables

Revision ID: 6a7b8c9d0e1f
Revises: 5f6a7b8c9d0e
Create Date: 2026-09-05 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a7b8c9d0e1f'
down_revision: Union[str, None] = '5f6a7b8c9d0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('employment_opportunities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('candidate_id', sa.String(length=128), nullable=False),
        sa.Column('vessel_id', sa.Integer(), nullable=False),
        sa.Column('cargo_id', sa.Integer(), nullable=True),
        sa.Column('employment_type', sa.String(length=64), nullable=False),
        sa.Column('origin_port_id', sa.Integer(), nullable=True),
        sa.Column('destination_port_id', sa.Integer(), nullable=True),
        sa.Column('availability_start', sa.DateTime(), nullable=False),
        sa.Column('availability_end', sa.DateTime(), nullable=True),
        sa.Column('employment_start', sa.DateTime(), nullable=True),
        sa.Column('employment_end', sa.DateTime(), nullable=True),
        sa.Column('delivery_deadline', sa.DateTime(), nullable=True),
        sa.Column('ballast_distance_nm', sa.Float(), nullable=True),
        sa.Column('ballast_days', sa.Float(), nullable=True),
        sa.Column('voyage_days', sa.Float(), nullable=True),
        sa.Column('idle_days', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('primary_reason_code', sa.String(length=64), nullable=True),
        sa.Column('primary_reason_description', sa.Text(), nullable=True),
        sa.Column('optimization_status', sa.String(length=64), nullable=False),
        sa.Column('economic_summary', sa.JSON(), nullable=True),
        sa.Column('timeline_detail', sa.JSON(), nullable=True),
        sa.Column('feasibility_detail', sa.JSON(), nullable=True),
        sa.Column('procurement_detail', sa.JSON(), nullable=True),
        sa.Column('provenance', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('runtime_mode', sa.Enum('LIVE', 'OFFLINE_DEMO', name='runtimemodeenum'), nullable=False),
        sa.ForeignKeyConstraint(['cargo_id'], ['cargo_parcels.id'], ),
        sa.ForeignKeyConstraint(['destination_port_id'], ['ports.id'], ),
        sa.ForeignKeyConstraint(['origin_port_id'], ['ports.id'], ),
        sa.ForeignKeyConstraint(['vessel_id'], ['vessel_profiles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('candidate_id')
    )
    op.create_index('ix_employment_opportunities_candidate_id', 'employment_opportunities', ['candidate_id'], unique=True)
    op.create_index('ix_employment_opportunities_cargo_id', 'employment_opportunities', ['cargo_id'], unique=False)
    op.create_index('ix_employment_opportunities_vessel_id', 'employment_opportunities', ['vessel_id'], unique=False)

    op.create_table('idle_assessments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('vessel_id', sa.Integer(), nullable=False),
        sa.Column('assessment_date', sa.DateTime(), nullable=False),
        sa.Column('window_start', sa.DateTime(), nullable=False),
        sa.Column('window_end', sa.DateTime(), nullable=True),
        sa.Column('available_days', sa.Float(), nullable=False),
        sa.Column('idle_days', sa.Float(), nullable=False),
        sa.Column('idle_reason', sa.String(length=64), nullable=False),
        sa.Column('daily_idle_rate', sa.Float(), nullable=False),
        sa.Column('idle_cost', sa.Float(), nullable=False),
        sa.Column('cost_source', sa.String(length=64), nullable=False),
        sa.Column('next_commitment_id', sa.Integer(), nullable=True),
        sa.Column('next_commitment_start', sa.DateTime(), nullable=True),
        sa.Column('advisory_notes', sa.Text(), nullable=True),
        sa.Column('provenance', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('runtime_mode', sa.Enum('LIVE', 'OFFLINE_DEMO', name='runtimemodeenum'), nullable=False),
        sa.ForeignKeyConstraint(['next_commitment_id'], ['vessel_commitments.id'], ),
        sa.ForeignKeyConstraint(['vessel_id'], ['vessel_profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_idle_assessments_vessel_id', 'idle_assessments', ['vessel_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_idle_assessments_vessel_id', table_name='idle_assessments')
    op.drop_table('idle_assessments')
    op.drop_index('ix_employment_opportunities_vessel_id', table_name='employment_opportunities')
    op.drop_index('ix_employment_opportunities_cargo_id', table_name='employment_opportunities')
    op.drop_index('ix_employment_opportunities_candidate_id', table_name='employment_opportunities')
    op.drop_table('employment_opportunities')
