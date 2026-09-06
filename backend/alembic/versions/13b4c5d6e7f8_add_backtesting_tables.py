"""add_backtesting_tables

Revision ID: 13b4c5d6e7f8
Revises: 12a3b4c5d6e7
Create Date: 2026-09-06 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13b4c5d6e7f8'
down_revision: Union[str, None] = '12a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create backtest_configurations table
    op.create_table(
        'backtest_configurations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('config_code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start_timestamp', sa.DateTime(), nullable=False),
        sa.Column('end_timestamp', sa.DateTime(), nullable=False),
        sa.Column('decision_frequency', sa.String(length=32), nullable=False, server_default='EVENT_DRIVEN'),
        sa.Column('decision_policy', sa.String(length=64), nullable=False, server_default='RECOMMENDED'),
        sa.Column('dataset_versions', sa.JSON(), nullable=False),
        sa.Column('phase7_configuration', sa.JSON(), nullable=True),
        sa.Column('phase8_enabled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('phase9_enabled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('phase10_configuration', sa.JSON(), nullable=True),
        sa.Column('benchmark_set', sa.JSON(), nullable=False),
        sa.Column('seed', sa.Integer(), nullable=False, server_default='42'),
        sa.Column('configuration_hash', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_configurations_config_code'), 'backtest_configurations', ['config_code'], unique=True)

    # 2. Extend backtest_runs with Phase 13 columns
    with op.batch_alter_table('backtest_runs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('run_code', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('configuration_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('mode', sa.String(length=32), nullable=False, server_default='DECISION_REPLAY'))
        batch_op.add_column(sa.Column('start_timestamp', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('end_timestamp', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('decision_frequency', sa.String(length=32), nullable=False, server_default='EVENT_DRIVEN'))
        batch_op.add_column(sa.Column('dataset_versions', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('backtest_hash', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('dataset_hash', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('configuration_hash', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('seed', sa.Integer(), nullable=False, server_default='42'))
        batch_op.add_column(sa.Column('software_version', sa.String(length=32), nullable=False, server_default='1.0.0'))
        batch_op.add_column(sa.Column('phase_versions', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('solver_version', sa.String(length=64), nullable=False, server_default='HiGHS-1.5.1'))
        batch_op.add_column(sa.Column('warnings_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('failure_reason', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('metrics_summary', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('execution_time_seconds', sa.Float(), nullable=True))
        batch_op.create_index(batch_op.f('ix_backtest_runs_run_code'), ['run_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_backtest_runs_configuration_id'), ['configuration_id'], unique=False)
        batch_op.create_foreign_key('fk_backtest_runs_configuration_id', 'backtest_configurations', ['configuration_id'], ['id'])

    # 3. Create backtest_snapshots table
    op.create_table(
        'backtest_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('snapshot_code', sa.String(length=64), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_timestamp', sa.DateTime(), nullable=False),
        sa.Column('dataset_versions', sa.JSON(), nullable=False),
        sa.Column('vessel_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cargo_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('market_state_hash', sa.String(length=128), nullable=True),
        sa.Column('snapshot_hash', sa.String(length=128), nullable=False),
        sa.Column('snapshot_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['backtest_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_snapshots_snapshot_code'), 'backtest_snapshots', ['snapshot_code'], unique=True)
    op.create_index(op.f('ix_backtest_snapshots_run_id'), 'backtest_snapshots', ['run_id'], unique=False)
    op.create_index(op.f('ix_backtest_snapshots_snapshot_timestamp'), 'backtest_snapshots', ['snapshot_timestamp'], unique=False)

    # 4. Create backtest_decisions table
    op.create_table(
        'backtest_decisions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('decision_code', sa.String(length=64), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_id', sa.Integer(), nullable=False),
        sa.Column('decision_timestamp', sa.DateTime(), nullable=False),
        sa.Column('phase7_run_id', sa.String(length=64), nullable=True),
        sa.Column('phase8_run_id', sa.String(length=64), nullable=True),
        sa.Column('phase9_run_id', sa.String(length=64), nullable=True),
        sa.Column('phase10_run_id', sa.String(length=64), nullable=True),
        sa.Column('recommendation', sa.String(length=32), nullable=False),
        sa.Column('assignments', sa.JSON(), nullable=False),
        sa.Column('expected_contribution', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('risk_metrics', sa.JSON(), nullable=True),
        sa.Column('governance_state', sa.JSON(), nullable=True),
        sa.Column('decision_hash', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['backtest_runs.id'], ),
        sa.ForeignKeyConstraint(['snapshot_id'], ['backtest_snapshots.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_decisions_decision_code'), 'backtest_decisions', ['decision_code'], unique=True)
    op.create_index(op.f('ix_backtest_decisions_run_id'), 'backtest_decisions', ['run_id'], unique=False)
    op.create_index(op.f('ix_backtest_decisions_snapshot_id'), 'backtest_decisions', ['snapshot_id'], unique=False)
    op.create_index(op.f('ix_backtest_decisions_decision_timestamp'), 'backtest_decisions', ['decision_timestamp'], unique=False)

    # 5. Create backtest_outcomes table
    op.create_table(
        'backtest_outcomes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('outcome_code', sa.String(length=64), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('decision_id', sa.Integer(), nullable=True),
        sa.Column('vessel_id', sa.Integer(), nullable=False),
        sa.Column('cargo_id', sa.Integer(), nullable=True),
        sa.Column('realized_revenue', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('realized_bunker_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('realized_port_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('realized_voyage_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('realized_ballast_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('realized_idle_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('realized_contribution', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('expected_contribution', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('economic_error', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('planned_departure', sa.DateTime(), nullable=True),
        sa.Column('actual_departure', sa.DateTime(), nullable=True),
        sa.Column('planned_arrival', sa.DateTime(), nullable=True),
        sa.Column('actual_arrival', sa.DateTime(), nullable=True),
        sa.Column('schedule_delay_days', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('idle_days', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('ballast_days', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cargo_completed', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('outcome_hash', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['backtest_runs.id'], ),
        sa.ForeignKeyConstraint(['decision_id'], ['backtest_decisions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_outcomes_outcome_code'), 'backtest_outcomes', ['outcome_code'], unique=True)
    op.create_index(op.f('ix_backtest_outcomes_run_id'), 'backtest_outcomes', ['run_id'], unique=False)
    op.create_index(op.f('ix_backtest_outcomes_decision_id'), 'backtest_outcomes', ['decision_id'], unique=False)

    # 6. Create backtest_benchmarks table
    op.create_table(
        'backtest_benchmarks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('benchmark_code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('strategy_type', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_benchmarks_benchmark_code'), 'backtest_benchmarks', ['benchmark_code'], unique=True)

    # 7. Create backtest_benchmark_results table
    op.create_table(
        'backtest_benchmark_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('benchmark_id', sa.Integer(), nullable=False),
        sa.Column('decision_id', sa.Integer(), nullable=True),
        sa.Column('step_timestamp', sa.DateTime(), nullable=False),
        sa.Column('assignments', sa.JSON(), nullable=False),
        sa.Column('realized_contribution', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('vessel_utilization', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['backtest_runs.id'], ),
        sa.ForeignKeyConstraint(['benchmark_id'], ['backtest_benchmarks.id'], ),
        sa.ForeignKeyConstraint(['decision_id'], ['backtest_decisions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_benchmark_results_run_id'), 'backtest_benchmark_results', ['run_id'], unique=False)
    op.create_index(op.f('ix_backtest_benchmark_results_benchmark_id'), 'backtest_benchmark_results', ['benchmark_id'], unique=False)
    op.create_index(op.f('ix_backtest_benchmark_results_step_timestamp'), 'backtest_benchmark_results', ['step_timestamp'], unique=False)

    # 8. Create backtest_metrics table
    op.create_table(
        'backtest_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('metric_category', sa.String(length=32), nullable=False),
        sa.Column('metric_name', sa.String(length=64), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['backtest_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_metrics_run_id'), 'backtest_metrics', ['run_id'], unique=False)

    # 9. Create backtest_attributions table
    op.create_table(
        'backtest_attributions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('attribution_type', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=False),
        sa.Column('entity_name', sa.String(length=255), nullable=False),
        sa.Column('incremental_contribution', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('decision_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('utilization_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['backtest_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_attributions_run_id'), 'backtest_attributions', ['run_id'], unique=False)

    # 10. Create backtest_leakages table
    op.create_table(
        'backtest_leakages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('decision_id', sa.Integer(), nullable=True),
        sa.Column('leakage_type', sa.String(length=64), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='CRITICAL'),
        sa.Column('field_name', sa.String(length=128), nullable=True),
        sa.Column('decision_timestamp', sa.DateTime(), nullable=False),
        sa.Column('information_timestamp', sa.DateTime(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['backtest_runs.id'], ),
        sa.ForeignKeyConstraint(['decision_id'], ['backtest_decisions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_leakages_run_id'), 'backtest_leakages', ['run_id'], unique=False)

    # 11. Create backtest_timelines table
    op.create_table(
        'backtest_timelines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=False),
        sa.Column('step_timestamp', sa.DateTime(), nullable=False),
        sa.Column('event_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['backtest_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_timelines_run_id'), 'backtest_timelines', ['run_id'], unique=False)
    op.create_index(op.f('ix_backtest_timelines_step_timestamp'), 'backtest_timelines', ['step_timestamp'], unique=False)


def downgrade() -> None:
    op.drop_table('backtest_timelines')
    op.drop_table('backtest_leakages')
    op.drop_table('backtest_attributions')
    op.drop_table('backtest_metrics')
    op.drop_table('backtest_benchmark_results')
    op.drop_table('backtest_benchmarks')
    op.drop_table('backtest_outcomes')
    op.drop_table('backtest_decisions')
    op.drop_table('backtest_snapshots')

    with op.batch_alter_table('backtest_runs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_backtest_runs_configuration_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_backtest_runs_configuration_id'))
        batch_op.drop_index(batch_op.f('ix_backtest_runs_run_code'))
        batch_op.drop_column('execution_time_seconds')
        batch_op.drop_column('metrics_summary')
        batch_op.drop_column('failure_reason')
        batch_op.drop_column('warnings_count')
        batch_op.drop_column('solver_version')
        batch_op.drop_column('phase_versions')
        batch_op.drop_column('software_version')
        batch_op.drop_column('seed')
        batch_op.drop_column('configuration_hash')
        batch_op.drop_column('dataset_hash')
        batch_op.drop_column('backtest_hash')
        batch_op.drop_column('dataset_versions')
        batch_op.drop_column('decision_frequency')
        batch_op.drop_column('end_timestamp')
        batch_op.drop_column('start_timestamp')
        batch_op.drop_column('mode')
        batch_op.drop_column('configuration_id')
        batch_op.drop_column('run_code')

    op.drop_table('backtest_configurations')
