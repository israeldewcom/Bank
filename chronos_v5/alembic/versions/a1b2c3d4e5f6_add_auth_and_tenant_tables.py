# alembic/versions/a1b2c3d4e5f6_add_auth_and_tenant_tables.py
"""add_auth_and_tenant_tables

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-07-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import uuid

# revision identifiers, used by Alembic.
#
# BUG FIX: this whole file previously used the literal placeholder string
# 'xxxx' as its revision id, and every migration in this directory
# (including this one) used the literal placeholder string
# 'previous_revision_id' as down_revision instead of a real parent hash.
# Two files (this one and add_execution_order_idempotency) both declared
# revision = 'xxxx', which is an outright collision — Alembic cannot build
# a linear history from that. `alembic upgrade head` would fail immediately,
# which is exactly why chronos_v5/database.py's run_migrations() has always
# silently fallen through to its `Base.metadata.create_all()` fallback in
# practice — nobody ever noticed migrations were broken because they never
# actually ran. Real, unique hex revision ids are used now, and the chain
# is wired: this file is the root (down_revision=None), followed by
# make_device_fingerprint_required, followed by
# add_execution_order_idempotency (ordered by each file's own Create Date).
revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add tenant column to existing tables
    op.add_column('trades', sa.Column('tenant', sa.String(50), nullable=False, server_default='default'))
    op.create_index(op.f('ix_trades_tenant'), 'trades', ['tenant'])
    op.add_column('pnl_attribution', sa.Column('tenant', sa.String(50), nullable=False, server_default='default'))
    op.create_index(op.f('ix_pnl_attribution_tenant'), 'pnl_attribution', ['tenant'])

    # SCHEMA FIX: this table previously used UUID(as_uuid=True) ids and a
    # hashed_password column with no is_active flag, while
    # chronos_v5/models.py's User ORM class — the schema the application
    # code actually queries against — used String(36) ids, password_hash,
    # and (until this pass) no status column at all. The two had drifted
    # into genuinely incompatible schemas. This migration now matches
    # models.py exactly: String(36) primary keys (UUIDs stored as text,
    # generated Python-side via default=uuid.uuid4 the same way the ORM
    # does), password_hash instead of hashed_password, and both status
    # (drives the approval workflow) and is_active (derived from status,
    # kept for the existing code paths that already read it) present
    # side by side rather than one or the other.
    op.create_table('users',
        sa.Column('id', sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255)),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'suspended', name='user_status'), nullable=False, server_default='pending'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('role', sa.Enum('user', 'developer', 'admin', name='user_role'), nullable=False, server_default='user'),
        sa.Column('trial_expiry', sa.DateTime, nullable=True),
        sa.Column('last_login', sa.DateTime, nullable=True),
        sa.Column('tenant', sa.String(50), nullable=False, server_default='default'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('approved_by', sa.String(36), nullable=True),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_tenant', 'users', ['tenant'])
    op.create_index('ix_users_status', 'users', ['status'])

    op.create_table('api_keys',
        sa.Column('id', sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('key_prefix', sa.String(20), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('tenant', sa.String(50), nullable=False, server_default='default'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('revoked_at', sa.DateTime, nullable=True),
        sa.Column('last_used_at', sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('ix_api_keys_tenant', 'api_keys', ['tenant'])
    op.create_index('ix_api_keys_key_prefix', 'api_keys', ['key_prefix'])

    op.create_table('devices',
        sa.Column('id', sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('device_name', sa.String(255)),
        sa.Column('device_fingerprint', sa.String(255)),
        sa.Column('status', sa.Enum('pending', 'approved', 'revoked', name='device_status'), nullable=False, server_default='pending'),
        sa.Column('tenant', sa.String(50), nullable=False, server_default='default'),
        sa.Column('requested_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('approved_by', sa.String(36), nullable=True),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        sa.Column('last_used_at', sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
    )
    op.create_index('ix_devices_tenant', 'devices', ['tenant'])

    op.create_table('pairing_codes',
        sa.Column('code', sa.String(10), primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=False),
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
