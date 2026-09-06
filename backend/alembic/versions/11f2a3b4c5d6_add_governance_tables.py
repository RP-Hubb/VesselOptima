"""add_governance_tables

Revision ID: 11f2a3b4c5d6
Revises: 10e1f2a3b4c5
Create Date: 2026-09-06 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '11f2a3b4c5d6'
down_revision: Union[str, None] = '10e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create decision_packages table
    op.create_table(
        'decision_packages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('package_id', sa.String(length=128), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('parent_package_id', sa.String(length=128), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=64), nullable=False, server_default='DRAFT'),
        sa.Column('optimization_run_id', sa.String(length=128), nullable=False),
        sa.Column('scenario_run_id', sa.String(length=128), nullable=True),
        sa.Column('risk_run_id', sa.String(length=128), nullable=True),
        sa.Column('decision_run_id', sa.String(length=128), nullable=False),
        sa.Column('configuration_id', sa.String(length=128), nullable=True),
        sa.Column('configuration_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('engine_versions', sa.JSON(), nullable=True),
        sa.Column('recommendation_type', sa.String(length=64), nullable=False),
        sa.Column('decision_score', sa.Float(), nullable=False),
        sa.Column('confidence', sa.String(length=32), nullable=False, server_default='HIGH'),
        sa.Column('decision_stability', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('expected_contribution', sa.Float(), nullable=False),
        sa.Column('risk_adjusted_contribution', sa.Float(), nullable=False),
        sa.Column('loss_probability', sa.Float(), nullable=False),
        sa.Column('cvar_95', sa.Float(), nullable=False),
        sa.Column('plan_reliability', sa.Float(), nullable=False),
        sa.Column('evidence_summary', sa.JSON(), nullable=True),
        sa.Column('actions_summary', sa.JSON(), nullable=True),
        sa.Column('threshold_config', sa.JSON(), nullable=True),
        sa.Column('input_hash', sa.String(length=128), nullable=False),
        sa.Column('output_hash', sa.String(length=128), nullable=False),
        sa.Column('package_hash', sa.String(length=128), nullable=False),
        sa.Column('created_by_role', sa.String(length=64), nullable=False, server_default='ANALYST'),
        sa.Column('is_override', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('audit_trail', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('runtime_mode', sa.Enum('LIVE', 'OFFLINE_DEMO', name='runtimemodeenum'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decision_packages_package_id', 'decision_packages', ['package_id'], unique=True)
    op.create_index('ix_decision_packages_parent_package_id', 'decision_packages', ['parent_package_id'], unique=False)
    op.create_index('ix_decision_packages_optimization_run_id', 'decision_packages', ['optimization_run_id'], unique=False)
    op.create_index('ix_decision_packages_decision_run_id', 'decision_packages', ['decision_run_id'], unique=False)

    # 2. Create decision_package_versions table
    op.create_table(
        'decision_package_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('package_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('version_tag', sa.String(length=64), nullable=False),
        sa.Column('parent_version_tag', sa.String(length=64), nullable=True),
        sa.Column('package_hash', sa.String(length=128), nullable=False),
        sa.Column('input_hash', sa.String(length=128), nullable=False),
        sa.Column('output_hash', sa.String(length=128), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=False),
        sa.Column('changed_fields', sa.JSON(), nullable=True),
        sa.Column('evidence_snapshot', sa.JSON(), nullable=False),
        sa.Column('configuration_version', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['package_id'], ['decision_packages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decision_package_versions_package_id', 'decision_package_versions', ['package_id'], unique=False)

    # 3. Create governance_audit_events table
    op.create_table(
        'governance_audit_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('package_id', sa.Integer(), nullable=False),
        sa.Column('audit_event_id', sa.String(length=128), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('actor', sa.String(length=255), nullable=False),
        sa.Column('actor_role', sa.String(length=64), nullable=False),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('previous_hash', sa.String(length=128), nullable=False),
        sa.Column('event_hash', sa.String(length=128), nullable=False),
        sa.Column('metadata_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['package_id'], ['decision_packages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_governance_audit_events_package_id', 'governance_audit_events', ['package_id'], unique=False)
    op.create_index('ix_governance_audit_events_audit_event_id', 'governance_audit_events', ['audit_event_id'], unique=True)

    # 4. Create approval_actions table
    op.create_table(
        'approval_actions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('package_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('actor', sa.String(length=255), nullable=False),
        sa.Column('actor_role', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=64), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['package_id'], ['decision_packages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_approval_actions_package_id', 'approval_actions', ['package_id'], unique=False)

    # 5. Create decision_configurations table
    op.create_table(
        'decision_configurations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('configuration_id', sa.String(length=128), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='ACTIVE'),
        sa.Column('economic_weight', sa.Float(), nullable=False, server_default='0.35'),
        sa.Column('reliability_weight', sa.Float(), nullable=False, server_default='0.25'),
        sa.Column('robustness_weight', sa.Float(), nullable=False, server_default='0.20'),
        sa.Column('tail_risk_weight', sa.Float(), nullable=False, server_default='0.10'),
        sa.Column('schedule_weight', sa.Float(), nullable=False, server_default='0.10'),
        sa.Column('recommendation_thresholds', sa.JSON(), nullable=False),
        sa.Column('confidence_thresholds', sa.JSON(), nullable=False),
        sa.Column('risk_thresholds', sa.JSON(), nullable=False),
        sa.Column('config_hash', sa.String(length=128), nullable=False),
        sa.Column('effective_date', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decision_configurations_configuration_id', 'decision_configurations', ['configuration_id'], unique=True)

    # 6. Create configuration_changes table
    op.create_table(
        'configuration_changes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('change_id', sa.String(length=128), nullable=False),
        sa.Column('old_configuration_id', sa.String(length=128), nullable=True),
        sa.Column('new_configuration_id', sa.String(length=128), nullable=False),
        sa.Column('changed_fields', sa.JSON(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('actor', sa.String(length=255), nullable=False),
        sa.Column('actor_role', sa.String(length=64), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_configuration_changes_change_id', 'configuration_changes', ['change_id'], unique=True)

    # 7. Create decision_overrides table
    op.create_table(
        'decision_overrides',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('package_id', sa.Integer(), nullable=False),
        sa.Column('override_id', sa.String(length=128), nullable=False),
        sa.Column('original_recommendation', sa.String(length=64), nullable=False),
        sa.Column('override_recommendation', sa.String(length=64), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('actor', sa.String(length=255), nullable=False),
        sa.Column('actor_role', sa.String(length=64), nullable=False),
        sa.Column('supporting_note', sa.Text(), nullable=True),
        sa.Column('approval_actor', sa.String(length=255), nullable=True),
        sa.Column('approval_status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['package_id'], ['decision_packages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decision_overrides_package_id', 'decision_overrides', ['package_id'], unique=False)
    op.create_index('ix_decision_overrides_override_id', 'decision_overrides', ['override_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_decision_overrides_override_id', table_name='decision_overrides')
    op.drop_index('ix_decision_overrides_package_id', table_name='decision_overrides')
    op.drop_table('decision_overrides')

    op.drop_index('ix_configuration_changes_change_id', table_name='configuration_changes')
    op.drop_table('configuration_changes')

    op.drop_index('ix_decision_configurations_configuration_id', table_name='decision_configurations')
    op.drop_table('decision_configurations')

    op.drop_index('ix_approval_actions_package_id', table_name='approval_actions')
    op.drop_table('approval_actions')

    op.drop_index('ix_governance_audit_events_audit_event_id', table_name='governance_audit_events')
    op.drop_index('ix_governance_audit_events_package_id', table_name='governance_audit_events')
    op.drop_table('governance_audit_events')

    op.drop_index('ix_decision_package_versions_package_id', table_name='decision_package_versions')
    op.drop_table('decision_package_versions')

    op.drop_index('ix_decision_packages_decision_run_id', table_name='decision_packages')
    op.drop_index('ix_decision_packages_optimization_run_id', table_name='decision_packages')
    op.drop_index('ix_decision_packages_parent_package_id', table_name='decision_packages')
    op.drop_index('ix_decision_packages_package_id', table_name='decision_packages')
    op.drop_table('decision_packages')
