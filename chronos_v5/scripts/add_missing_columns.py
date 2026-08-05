# chronos_v5/scripts/add_missing_columns.py
import os
import sqlalchemy as sa
from sqlalchemy import text
from chronos_v5.config import Config

def add_missing_columns():
    """Add status and is_active columns to the users table if they don't exist."""
    engine = sa.create_engine(Config.DATABASE_URL)
    with engine.connect() as conn:
        # Check if status column exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='status'
            )
        """))
        status_exists = result.scalar()
        if not status_exists:
            print("Adding 'status' column to users table...")
            conn.execute(text("""
                ALTER TABLE users ADD COLUMN status VARCHAR(20) DEFAULT 'pending' NOT NULL
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_status ON users (status)"))
            print("✅ 'status' column added.")
        else:
            print("ℹ️ 'status' column already exists, skipping.")

        # Check if is_active column exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='is_active'
            )
        """))
        is_active_exists = result.scalar()
        if not is_active_exists:
            print("Adding 'is_active' column to users table...")
            conn.execute(text("""
                ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT FALSE
            """))
            print("✅ 'is_active' column added.")
        else:
            print("ℹ️ 'is_active' column already exists, skipping.")

        # Ensure no NULLs
        conn.execute(text("UPDATE users SET status = 'pending' WHERE status IS NULL"))
        conn.execute(text("UPDATE users SET is_active = FALSE WHERE is_active IS NULL"))
        conn.commit()
        print("✅ All columns are up to date.")

if __name__ == "__main__":
    add_missing_columns()
