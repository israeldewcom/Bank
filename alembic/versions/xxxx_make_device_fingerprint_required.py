# alembic/versions/xxxx_make_device_fingerprint_required.py
"""make_device_fingerprint_required

Revision ID: xxxx
Revises: <previous_revision_id>
Create Date: 2026-07-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'xxxx'
down_revision = 'previous_revision_id'  # set to the last revision
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
