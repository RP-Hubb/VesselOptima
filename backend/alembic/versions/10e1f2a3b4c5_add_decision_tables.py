"""add_decision_tables

Revision ID: 10e1f2a3b4c5
Revises: 9d0e1f2a3b4c
Create Date: 2026-09-06 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10e1f2a3b4c5'
down_revision: Union[str, None] = '9d0e1f2a3b4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create decision_runs table
    op.create_table(
        'decision_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.String(length=128), nullable=False),
        sa.Column('optimization_run_id', sa.String(length=128), nullable=False),
        sa.Column('scenario_run_id', sa.String(length=128), nullable=True),
        sa.Column('risk_run_id', sa.String(length=128), nullable=True),
        sa.Column('recommendation_type', sa.String(length=64), nullable=False),
        sa.Column('confidence', sa.String(length=32), nullable=False, server_default='HIGH'),
        sa.Column('decision_score', sa.Float(), nullable=False),
        sa.Column('decision_stability', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('scoring_breakdown', sa.JSON(), nullable=True),
        sa.Column('risk_adjusted_contribution', sa.Float(), nullable=True),
        sa.Column('threshold_config', sa.JSON(), nullable=True),
        sa.Column('engine_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('rule_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('score_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('input_hash', sa.String(length=128), nullable=True),
        sa.Column('output_hash', sa.String(length=128), nullable=True),
        sa.Column('audit_trail', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='COMPLETED'),
        sa.Column('execution_time_seconds', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('runtime_mode', sa.Enum('LIVE', 'OFFLINE_DEMO', name='runtimemodeenum'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decision_runs_run_id', 'decision_runs', ['run_id'], unique=True)
    op.create_index('ix_decision_runs_optimization_run_id', 'decision_runs', ['optimization_run_id'], unique=False)
    op.create_index('ix_decision_runs_scenario_run_id', 'decision_runs', ['scenario_run_id'], unique=False)
    op.create_index('ix_decision_runs_risk_run_id', 'decision_runs', ['risk_run_id'], unique=False)

    # 2. Create decision_recommendations table
    op.create_table(
        'decision_recommendations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('decision_run_id', sa.Integer(), nullable=False),
        sa.Column('scope', sa.String(length=32), nullable=False, server_default='PLAN'),
        sa.Column('candidate_id', sa.String(length=128), nullable=True),
        sa.Column('vessel_id', sa.Integer(), nullable=True),
        sa.Column('cargo_id', sa.Integer(), nullable=True),
        sa.Column('recommendation_type', sa.String(length=64), nullable=False),
        sa.Column('primary_reason_code', sa.String(length=64), nullable=False),
        sa.Column('reason_codes', sa.JSON(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('action_advice', sa.Text(), nullable=True),
        sa.Column('supporting_metrics', sa.JSON(), nullable=True),
        sa.Column('thresholds_used', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['decision_run_id'], ['decision_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vessel_id'], ['vessel_profiles.id']),
        sa.ForeignKeyConstraint(['cargo_id'], ['cargo_parcels.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decision_recommendations_decision_run_id', 'decision_recommendations', ['decision_run_id'], unique=False)
    op.create_index('ix_decision_recommendations_candidate_id', 'decision_recommendations', ['candidate_id'], unique=False)

    # 3. Create decision_evidence table
    op.create_table(
        'decision_evidence',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('decision_run_id', sa.Integer(), nullable=False),
        sa.Column('optimization_objective', sa.Float(), nullable=True),
        sa.Column('expected_contribution', sa.Float(), nullable=False),
        sa.Column('baseline_contribution', sa.Float(), nullable=True),
        sa.Column('risk_adjusted_contribution', sa.Float(), nullable=False),
        sa.Column('loss_probability', sa.Float(), nullable=False),
        sa.Column('cvar_95', sa.Float(), nullable=False),
        sa.Column('var_95_downside', sa.Float(), nullable=False),
        sa.Column('assignment_survival', sa.Float(), nullable=False),
        sa.Column('plan_reliability', sa.Float(), nullable=False),
        sa.Column('laycan_miss_probability', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('scenario_survival_rate', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('robustness_tier', sa.String(length=64), nullable=False, server_default='CORE_ROBUST'),
        sa.Column('top_risk_drivers', sa.JSON(), nullable=True),
        sa.Column('critical_warnings', sa.JSON(), nullable=True),
        sa.Column('evidence_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['decision_run_id'], ['decision_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decision_evidence_decision_run_id', 'decision_evidence', ['decision_run_id'], unique=True)

    # 4. Create decision_actions table
    op.create_table(
        'decision_actions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('decision_run_id', sa.Integer(), nullable=False),
        sa.Column('action_id', sa.String(length=128), nullable=False),
        sa.Column('priority', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('affected_variable', sa.String(length=128), nullable=True),
        sa.Column('affected_assignment_id', sa.String(length=128), nullable=True),
        sa.Column('trigger_condition', sa.Text(), nullable=True),
        sa.Column('recommended_action', sa.Text(), nullable=False),
        sa.Column('action_status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['decision_run_id'], ['decision_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decision_actions_decision_run_id', 'decision_actions', ['decision_run_id'], unique=False)

    # 5. Create decision_tradeoffs table
    op.create_table(
        'decision_tradeoffs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('decision_run_id', sa.Integer(), nullable=False),
        sa.Column('comparison_plan_id', sa.String(length=128), nullable=False),
        sa.Column('comparison_plan_name', sa.String(length=255), nullable=False),
        sa.Column('baseline_plan_name', sa.String(length=255), nullable=False),
        sa.Column('contribution_delta', sa.Float(), nullable=False),
        sa.Column('loss_prob_delta', sa.Float(), nullable=False),
        sa.Column('cvar_delta', sa.Float(), nullable=False),
        sa.Column('reliability_delta', sa.Float(), nullable=False),
        sa.Column('tradeoff_summary', sa.Text(), nullable=False),
        sa.Column('tradeoff_details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['decision_run_id'], ['decision_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decision_tradeoffs_decision_run_id', 'decision_tradeoffs', ['decision_run_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_decision_tradeoffs_decision_run_id', table_name='decision_tradeoffs')
    op.drop_table('decision_tradeoffs')

    op.drop_index('ix_decision_actions_decision_run_id', table_name='decision_actions')
    op.drop_table('decision_actions')

    op.drop_index('ix_decision_evidence_decision_run_id', table_name='decision_evidence')
    op.drop_table('decision_evidence')

    op.drop_index('ix_decision_recommendations_candidate_id', table_name='decision_recommendations')
    op.drop_index('ix_decision_recommendations_decision_run_id', table_name='decision_recommendations')
    op.drop_table('decision_recommendations')

    op.drop_index('ix_decision_runs_risk_run_id', table_name='decision_runs')
    op.drop_index('ix_decision_runs_scenario_run_id', table_name='decision_runs')
    op.drop_index('ix_decision_runs_optimization_run_id', table_name='decision_runs')
    op.drop_index('ix_decision_runs_run_id', table_name='decision_runs')
    op.drop_table('decision_runs')
