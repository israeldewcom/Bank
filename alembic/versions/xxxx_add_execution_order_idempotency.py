# alembic/versions/xxxx_add_execution_order_idempotency.py
"""add_execution_order_idempotency

Revision ID: xxxx
Revises: <previous_revision_id>
Create Date: 2026-07-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'xxxx'
down_revision = 'previous_revision_id'  # set to the last revision
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('execution_orders', sa.Column('tenant', sa.String(length=100), nullable=True))
    op.add_column('execution_orders', sa.Column('client_order_id', sa.String(length=64), nullable=True))
    op.add_column('execution_orders', sa.Column('gateway_response', sa.JSON(), nullable=True))

    # Backfill required columns before enforcing NOT NULL / UNIQUE, since existing
    # rows (if any) won't have a client_order_id yet.
    op.execute("""
        UPDATE execution_orders
        SET client_order_id = trade_id || ':' || id::text
        WHERE client_order_id IS NULL
    """)
    op.execute("""
        UPDATE execution_orders
        SET tenant = 'default'
        WHERE tenant IS NULL
    """)

    op.alter_column('execution_orders', 'tenant', nullable=False)
    op.alter_column('execution_orders', 'client_order_id', nullable=False)

    op.create_index(
        'ix_execution_orders_tenant', 'execution_orders', ['tenant']
    )
    op.create_unique_constraint(
        'uq_execution_orders_client_order_id', 'execution_orders', ['client_order_id']
    )
    op.create_index(
        'ix_execution_orders_client_order_id', 'execution_orders', ['client_order_id']
    )


def downgrade():
    op.drop_index('ix_execution_orders_client_order_id', table_name='execution_orders')
    op.drop_constraint('uq_execution_orders_client_order_id', 'execution_orders', type_='unique')
    op.drop_index('ix_execution_orders_tenant', table_name='execution_orders')
    op.drop_column('execution_orders', 'gateway_response')
    op.drop_column('execution_orders', 'client_order_id')
    op.drop_column('execution_orders', 'tenant')
