"""Initial database setup with all tables

Revision ID: 001
Revises: 
Create Date: 2025-05-29 13:36:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create all initial tables for Origami Composer
    """
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('alpaca_oauth_token', sa.Text(), nullable=True),
        sa.Column('alpaca_refresh_token', sa.Text(), nullable=True),
        sa.Column('alpaca_token_scope', sa.String(length=255), nullable=True),
        sa.Column('alpaca_token_expiry', sa.DateTime(timezone=True), nullable=True),
        sa.Column('oauth_connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('preferred_theme', sa.String(length=20), nullable=False, default='light'),
        sa.Column('email_notifications', sa.Boolean(), nullable=False, default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Create symphony status enum
    symphony_status = postgresql.ENUM('active', 'inactive', 'stopped', 'error', name='symphonystatus')
    symphony_status.create(op.get_bind())
    
    # Create symphonies table
    op.create_table('symphonies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', symphony_status, nullable=False, default='inactive'),
        sa.Column('json_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('last_executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_execution_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_count', sa.Integer(), nullable=False, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_symphonies_status'), 'symphonies', ['status'], unique=False)
    op.create_index(op.f('ix_symphonies_user_id'), 'symphonies', ['user_id'], unique=False)
    
    # Create positions table
    op.create_table('positions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('symphony_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('average_cost', sa.Float(), nullable=False),
        sa.Column('current_price', sa.Float(), nullable=False),
        sa.Column('market_value', sa.Float(), nullable=False),
        sa.Column('cost_basis', sa.Float(), nullable=False),
        sa.Column('unrealized_pnl', sa.Float(), nullable=False),
        sa.Column('unrealized_pnl_percent', sa.Float(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['symphony_id'], ['symphonies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_positions_symphony_timestamp', 'positions', ['symphony_id', 'timestamp'], unique=False)
    op.create_index('idx_positions_symbol', 'positions', ['symbol'], unique=False)
    op.create_index(op.f('ix_positions_timestamp'), 'positions', ['timestamp'], unique=False)
    
    # Create trade side and status enums
    trade_side = postgresql.ENUM('buy', 'sell', name='tradeside')
    trade_side.create(op.get_bind())
    trade_status = postgresql.ENUM('pending', 'filled', 'partial', 'cancelled', 'rejected', name='tradestatus')
    trade_status.create(op.get_bind())
    
    # Create trades table
    op.create_table('trades',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('symphony_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('side', trade_side, nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('commission', sa.Float(), nullable=False, default=0.0),
        sa.Column('status', trade_status, nullable=False, default='pending'),
        sa.Column('order_id', sa.String(length=100), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('algorithm_decision', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('rebalance_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['symphony_id'], ['symphonies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id')
    )
    op.create_index('idx_trades_symphony_executed', 'trades', ['symphony_id', 'executed_at'], unique=False)
    op.create_index('idx_trades_symbol', 'trades', ['symbol'], unique=False)
    op.create_index(op.f('ix_trades_executed_at'), 'trades', ['executed_at'], unique=False)
    op.create_index(op.f('ix_trades_order_id'), 'trades', ['order_id'], unique=True)
    
    # Create metric type and time frame enums
    metric_type = postgresql.ENUM('total_return', 'daily_return', 'cumulative_return', 'sharpe_ratio', 
                                  'sortino_ratio', 'calmar_ratio', 'max_drawdown', 'volatility', 
                                  'win_rate', 'profit_factor', 'expected_return', 'value_at_risk', 
                                  'beta', 'alpha', 'portfolio_value', name='metrictype')
    metric_type.create(op.get_bind())
    time_frame = postgresql.ENUM('daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'all_time', name='timeframe')
    time_frame.create(op.get_bind())
    
    # Create performance_metrics table
    op.create_table('performance_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('symphony_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_type', metric_type, nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('time_frame', time_frame, nullable=False, default='daily'),
        sa.Column('benchmark_symbol', sa.String(length=20), nullable=False, default='SPY'),
        sa.Column('benchmark_value', sa.Float(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['symphony_id'], ['symphonies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_performance_symphony_calculated', 'performance_metrics', 
                    ['symphony_id', 'calculated_at'], unique=False)
    op.create_index('idx_performance_symphony_metric', 'performance_metrics', 
                    ['symphony_id', 'metric_type'], unique=False)
    op.create_index(op.f('ix_performance_metrics_calculated_at'), 'performance_metrics', 
                    ['calculated_at'], unique=False)
    
    # Create backtests table
    op.create_table('backtests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('symphony_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('initial_capital', sa.Float(), nullable=False, default=100000.0),
        sa.Column('final_value', sa.Float(), nullable=False),
        sa.Column('total_return', sa.Float(), nullable=False),
        sa.Column('total_trades', sa.Float(), nullable=False, default=0),
        sa.Column('algorithm_decisions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('performance_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('execution_time_seconds', sa.Float(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['symphony_id'], ['symphonies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtests_symphony_id'), 'backtests', ['symphony_id'], unique=False)


def downgrade() -> None:
    """
    Drop all tables and custom types
    """
    # Drop tables
    op.drop_table('backtests')
    op.drop_table('performance_metrics')
    op.drop_table('trades')
    op.drop_table('positions')
    op.drop_table('symphonies')
    op.drop_table('users')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS metrictype")
    op.execute("DROP TYPE IF EXISTS timeframe")
    op.execute("DROP TYPE IF EXISTS tradestatus")
    op.execute("DROP TYPE IF EXISTS tradeside")
    op.execute("DROP TYPE IF EXISTS symphonystatus")
