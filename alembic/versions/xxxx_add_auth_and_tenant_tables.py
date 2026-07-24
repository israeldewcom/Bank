# alembic/versions/xxxx_add_auth_and_tenant_tables.py
"""add_auth_and_tenant_tables

Revision ID: xxxx
Revises: 
Create Date: 2026-07-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = 'xxxx'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add tenant column to existing tables
    op.add_column('trades', sa.Column('tenant', sa.String(50), nullable=False, server_default='default'))
    op.create_index(op.f('ix_trades_tenant'), 'trades', ['tenant'])
    op.add_column('pnl_attribution', sa.Column('tenant', sa.String(50), nullable=False, server_default='default'))
    op.create_index(op.f('ix_pnl_attribution_tenant'), 'pnl_attribution', ['tenant'])

    # Create new tables
    op.create_table('users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255)),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'suspended', name='user_status'), nullable=False, server_default='pending'),
        sa.Column('role', sa.Enum('user', 'developer', 'admin', name='user_role'), nullable=False, server_default='user'),
        sa.Column('tenant', sa.String(50), nullable=False, server_default='default'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('approved_by', UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_tenant', 'users', ['tenant'])

    op.create_table('api_keys',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('key_prefix', sa.String(20), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('tenant', sa.String(50), nullable=False, server_default='default'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('revoked_at', sa.DateTime, nullable=True),
        sa.Column('last_used_at', sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('ix_api_keys_tenant', 'api_keys', ['tenant'])

    op.create_table('devices',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('device_name', sa.String(255)),
        sa.Column('device_fingerprint', sa.String(255)),
        sa.Column('status', sa.Enum('pending', 'approved', 'revoked', name='device_status'), nullable=False, server_default='pending'),
        sa.Column('tenant', sa.String(50), nullable=False, server_default='default'),
        sa.Column('requested_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('approved_by', UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        sa.Column('last_used_at', sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
    )
    op.create_index('ix_devices_tenant', 'devices', ['tenant'])

    op.create_table('pairing_codes',
        sa.Column('code', sa.String(10), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('device_name', sa.String(255)),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('consumed', sa.Boolean, default=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )

    op.create_table('tenant_configs',
        sa.Column('tenant', sa.String(50), primary_key=True),
        sa.Column('performance_fee_percent', sa.Float, default=0.20),
        sa.Column('bloomberg_api_key_enc', sa.Text, nullable=True),
        sa.Column('reuters_api_key_enc', sa.Text, nullable=True),
        sa.Column('alpha_vantage_key_enc', sa.Text, nullable=True),
        sa.Column('nibss_api_key_enc', sa.Text, nullable=True),
        sa.Column('cbn_openapi_url', sa.String(255), nullable=True),
        sa.Column('ngx_api_url', sa.String(255), nullable=True),
        sa.Column('use_global_model', sa.Boolean, default=True),
        sa.Column('alpha_strategy_type', sa.String(50), nullable=True),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

def downgrade():
    op.drop_table('tenant_configs')
    op.drop_table('pairing_codes')
    op.drop_table('devices')
    op.drop_table('api_keys')
    op.drop_table('users')
    op.drop_index('ix_pnl_attribution_tenant', table_name='pnl_attribution')
    op.drop_column('pnl_attribution', 'tenant')
    op.drop_index('ix_trades_tenant', table_name='trades')
    op.drop_column('trades', 'tenant')
    # Drop enums
    sa.Enum('pending', 'approved', 'rejected', 'suspended', name='user_status').drop(op.get_bind())
    sa.Enum('user', 'developer', 'admin', name='user_role').drop(op.get_bind())
    sa.Enum('pending', 'approved', 'revoked', name='device_status').drop(op.get_bind())
