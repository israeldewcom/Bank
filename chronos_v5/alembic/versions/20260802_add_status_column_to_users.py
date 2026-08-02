"""add_status_column_to_users

Revision ID: 20260802_add_status
Revises: a1b2c3d4e5f6   # or the latest revision you have; adjust if needed
Create Date: 2026-08-02 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '20260802_add_status'
down_revision = 'a1b2c3d4e5f6'   # Change to the last applied revision, or None if starting fresh
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    """Check if a column exists in the given table."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade():
    # Add status column to users table if it does not exist
    if not column_exists('users', 'status'):
        op.add_column('users', sa.Column('status', sa.String(20), nullable=False, server_default='pending'))
        op.create_index('ix_users_status', 'users', ['status'])
    else:
        print("Column 'status' already exists in 'users', skipping.")

    # Ensure is_active column exists (if missing for some reason)
    if not column_exists('users', 'is_active'):
        op.add_column('users', sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.false()))
        # Optionally, update is_active based on status (but we'll keep it simple)

    # If you also need to add other missing columns from the original migration, you can add them here

def downgrade():
    # Remove the status column if needed
    if column_exists('users', 'status'):
        op.drop_index('ix_users_status', table_name='users')
        op.drop_column('users', 'status')
    # We don't drop is_active in downgrade to avoid data loss; adjust as needed,
