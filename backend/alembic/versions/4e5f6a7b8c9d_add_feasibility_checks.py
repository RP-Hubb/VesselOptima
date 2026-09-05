"""add_feasibility_checks

Revision ID: 4e5f6a7b8c9d
Revises: 3d2cf736f21b
Create Date: 2026-09-05 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e5f6a7b8c9d'
down_revision: Union[str, None] = '3d2cf736f21b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('feasibility_checks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cargo_id', sa.Integer(), nullable=True),
        sa.Column('vessel_id', sa.Integer(), nullable=True),
        sa.Column('route_id', sa.Integer(), nullable=True),
        sa.Column('is_feasible', sa.Boolean(), nullable=False),
        sa.Column('primary_reason_code', sa.String(length=128), nullable=True),
        sa.Column('reason_codes', sa.JSON(), nullable=True),
        sa.Column('failed_checks', sa.JSON(), nullable=True),
        sa.Column('checks', sa.JSON(), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=True),
        sa.Column('timing', sa.JSON(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('provenance', sa.JSON(), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(), nullable=False),
        sa.Column('runtime_mode', sa.Enum('LIVE', 'OFFLINE_DEMO', name='runtimemodeenum'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['cargo_id'], ['cargo_parcels.id'], ),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ),
        sa.ForeignKeyConstraint(['vessel_id'], ['vessel_profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_feasibility_checks_cargo_id'), 'feasibility_checks', ['cargo_id'], unique=False)
    op.create_index(op.f('ix_feasibility_checks_vessel_id'), 'feasibility_checks', ['vessel_id'], unique=False)
    op.create_index(op.f('ix_feasibility_checks_route_id'), 'feasibility_checks', ['route_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_feasibility_checks_route_id'), table_name='feasibility_checks')
    op.drop_index(op.f('ix_feasibility_checks_vessel_id'), table_name='feasibility_checks')
    op.drop_index(op.f('ix_feasibility_checks_cargo_id'), table_name='feasibility_checks')
    op.drop_table('feasibility_checks')
