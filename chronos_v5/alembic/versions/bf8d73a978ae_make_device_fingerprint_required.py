# alembic/versions/bf8d73a978ae_make_device_fingerprint_required.py
"""make_device_fingerprint_required

Revision ID: bf8d73a978ae
Revises: a1b2c3d4e5f6
Create Date: 2026-07-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
#
# BUG FIX: this file previously declared revision = 'xxxx' — the exact
# same placeholder as add_auth_and_tenant_tables.py, an outright collision
# — and down_revision = 'previous_revision_id', a literal string rather
# than a real parent hash. Now points at a1b2c3d4e5f6
# (add_auth_and_tenant_tables), the migration that actually creates the
# devices table this one alters.
revision = 'bf8d73a978ae'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

def upgrade():
    # Change device_fingerprint column to NOT NULL
    op.alter_column('devices', 'device_fingerprint',
               existing_type=sa.String(255),
               nullable=False)

def downgrade():
    op.alter_column('devices', 'device_fingerprint',
               existing_type=sa.String(255),
               nullable=True)
