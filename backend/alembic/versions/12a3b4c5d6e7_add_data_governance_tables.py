"""add_data_governance_tables

Revision ID: 12a3b4c5d6e7
Revises: 11f2a3b4c5d6
Create Date: 2026-09-06 18:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12a3b4c5d6e7'
down_revision: Union[str, None] = '11f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create governance_datasets table
    op.create_table(
        'governance_datasets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.String(length=128), nullable=False),
        sa.Column('dataset_type', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('current_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='IMPORTED'),
        sa.Column('content_hash', sa.String(length=128), nullable=False),
        sa.Column('quality_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('freshness_status', sa.String(length=32), nullable=False, server_default='UNKNOWN'),
        sa.Column('record_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.String(length=255), nullable=False, server_default='data_engineer'),
        sa.Column('approved_by', sa.String(length=255), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('runtime_mode', sa.Enum('LIVE', 'OFFLINE_DEMO', name='runtimemodeenum'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_governance_datasets_dataset_id'), 'governance_datasets', ['dataset_id'], unique=True)
    op.create_index(op.f('ix_governance_datasets_dataset_type'), 'governance_datasets', ['dataset_type'], unique=False)
    op.create_index(op.f('ix_governance_datasets_status'), 'governance_datasets', ['status'], unique=False)

    # 2. Create dataset_versions table
    op.create_table(
        'dataset_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('parent_version_number', sa.Integer(), nullable=True),
        sa.Column('content_hash', sa.String(length=128), nullable=False),
        sa.Column('schema_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('record_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('storage_path', sa.String(length=512), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=False, server_default='data_engineer'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['governance_datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dataset_versions_dataset_id'), 'dataset_versions', ['dataset_id'], unique=False)

    # 3. Create dataset_records table
    op.create_table(
        'dataset_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('record_index', sa.Integer(), nullable=False),
        sa.Column('business_key', sa.String(length=255), nullable=True),
        sa.Column('record_data', sa.JSON(), nullable=False),
        sa.Column('record_hash', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['governance_datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dataset_records_dataset_id'), 'dataset_records', ['dataset_id'], unique=False)
    op.create_index(op.f('ix_dataset_records_business_key'), 'dataset_records', ['business_key'], unique=False)

    # 4. Create dataset_validations table
    op.create_table(
        'dataset_validations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('layer', sa.String(length=32), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('warning_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['governance_datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dataset_validations_dataset_id'), 'dataset_validations', ['dataset_id'], unique=False)

    # 5. Create dataset_qualities table
    op.create_table(
        'dataset_qualities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('completeness_score', sa.Float(), nullable=False),
        sa.Column('validity_score', sa.Float(), nullable=False),
        sa.Column('consistency_score', sa.Float(), nullable=False),
        sa.Column('uniqueness_score', sa.Float(), nullable=False),
        sa.Column('timeliness_score', sa.Float(), nullable=False),
        sa.Column('provenance_score', sa.Float(), nullable=False),
        sa.Column('weights_snapshot', sa.JSON(), nullable=True),
        sa.Column('freshness_status', sa.String(length=32), nullable=False),
        sa.Column('evaluated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['governance_datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dataset_qualities_dataset_id'), 'dataset_qualities', ['dataset_id'], unique=False)

    # 6. Create dataset_provenances table
    op.create_table(
        'dataset_provenances',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('source_name', sa.String(length=255), nullable=False),
        sa.Column('source_type', sa.String(length=64), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('original_hash', sa.String(length=128), nullable=True),
        sa.Column('import_actor', sa.String(length=255), nullable=False),
        sa.Column('import_timestamp', sa.DateTime(), nullable=False),
        sa.Column('schema_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('parent_dataset_id', sa.String(length=128), nullable=True),
        sa.Column('transformation_chain', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['governance_datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dataset_provenances_dataset_id'), 'dataset_provenances', ['dataset_id'], unique=True)

    # 7. Create quarantine_records table
    op.create_table(
        'quarantine_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('record_identifier', sa.String(length=255), nullable=True),
        sa.Column('field_name', sa.String(length=128), nullable=True),
        sa.Column('original_value', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='ROW_QUARANTINE'),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('raw_record', sa.JSON(), nullable=True),
        sa.Column('quarantined_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['governance_datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quarantine_records_dataset_id'), 'quarantine_records', ['dataset_id'], unique=False)

    # 8. Create dataset_changes table
    op.create_table(
        'dataset_changes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('base_version', sa.Integer(), nullable=False),
        sa.Column('target_version', sa.Integer(), nullable=False),
        sa.Column('change_type', sa.String(length=32), nullable=False),
        sa.Column('record_identifier', sa.String(length=255), nullable=False),
        sa.Column('field_diffs', sa.JSON(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['governance_datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dataset_changes_dataset_id'), 'dataset_changes', ['dataset_id'], unique=False)

    # 9. Create dataset_impacts table
    op.create_table(
        'dataset_impacts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('impact_level', sa.String(length=32), nullable=False, server_default='LOW'),
        sa.Column('affected_engines', sa.JSON(), nullable=False),
        sa.Column('affected_runs', sa.JSON(), nullable=True),
        sa.Column('requires_recalculation', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('stale_decision_packages', sa.JSON(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('analyzed_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['governance_datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dataset_impacts_dataset_id'), 'dataset_impacts', ['dataset_id'], unique=False)


def downgrade() -> None:
    op.drop_table('dataset_impacts')
    op.drop_table('dataset_changes')
    op.drop_table('quarantine_records')
    op.drop_table('dataset_provenances')
    op.drop_table('dataset_qualities')
    op.drop_table('dataset_validations')
    op.drop_table('dataset_records')
    op.drop_table('dataset_versions')
    op.drop_table('governance_datasets')
