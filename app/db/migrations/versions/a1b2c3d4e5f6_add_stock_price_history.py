"""add_stock_price_history

Revision ID: a1b2c3d4e5f6
Revises: f23e32a2f176
Create Date: 2026-04-04

Adds the stock_price_history table for persistent OHLCV candle storage.
Every market-data fetch upserts candles here so history accumulates locally.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f23e32a2f176'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        'stock_price_history',
        sa.Column('id',           sa.Integer(),  nullable=False),
        sa.Column('stock_id',     sa.Integer(),  nullable=False),
        sa.Column('interval',     sa.String(10), nullable=False),
        sa.Column('bar_datetime', sa.DateTime(), nullable=False),
        sa.Column('open',         sa.Float(),    nullable=False),
        sa.Column('high',         sa.Float(),    nullable=False),
        sa.Column('low',          sa.Float(),    nullable=False),
        sa.Column('close',        sa.Float(),    nullable=False),
        sa.Column('volume',       sa.Float(),    nullable=True),
        sa.Column('saved_at',     sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'interval', 'bar_datetime',
                            name='uq_price_history_stock_interval_dt'),
    )
    op.create_index('ix_price_history_lookup', 'stock_price_history',
                    ['stock_id', 'interval', 'bar_datetime'])
    op.create_index(op.f('ix_stock_price_history_id'), 'stock_price_history', ['id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_stock_price_history_id'), table_name='stock_price_history')
    op.drop_index('ix_price_history_lookup', table_name='stock_price_history')
    op.drop_table('stock_price_history')
