"""add_missing_status_column

Revision ID: 20260802_add_missing_status
Revises: a1b2c3d4e5f6  # Adjust to your last successful migration
Create Date: 2026-08-02 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '20260802_add_missing_status'
down_revision = 'a1b2c3d4e5f6'  # Change to your latest migration ID
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
        print("✅ Added 'status' column to users table")
    else:
        print("ℹ️ Column 'status' already exists, skipping")

    # Ensure is_active column exists
    if not column_exists('users', 'is_active'):
        op.add_column('users', sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.false()))
        print("✅ Added 'is_active' column to users table")
    else:
        print("ℹ️ Column 'is_active' already exists, skipping")

    # Update any existing rows to have default status if they somehow have NULL
    op.execute("UPDATE users SET status = 'pending' WHERE status IS NULL")
    op.execute("UPDATE users SET is_active = FALSE WHERE is_active IS NULL")

def downgrade():
    # Only remove status column if it exists
    if column_exists('users', 'status'):
        op.drop_index('ix_users_status', table_name='users')
        op.drop_column('users', 'status')
        print("⬇️ Removed 'status' column")

    # Optionally remove is_active (but be careful with data loss)
    # if column_exists('users', 'is_active'):
    #     op.drop_column('users', 'is_active')
    #     print("⬇️ Removed 'is_active' column")
