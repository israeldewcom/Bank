# chronos_v5/scripts/add_missing_columns.py
import os
import sqlalchemy as sa
from sqlalchemy import text
from chronos_v5.config import Config

def add_missing_columns():
    """Add missing columns to the users and trades tables if they don't exist."""
    engine = sa.create_engine(Config.DATABASE_URL)
    with engine.connect() as conn:
        # ---- USERS ----
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

        # ---- TRADES ----
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='trades' AND column_name='tenant'
            )
        """))
        tenant_exists = result.scalar()
        if not tenant_exists:
            print("Adding 'tenant' column to trades table...")
            conn.execute(text("""
                ALTER TABLE trades ADD COLUMN tenant VARCHAR(50) DEFAULT 'default' NOT NULL
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_trades_tenant ON trades (tenant)"))
            print("✅ 'tenant' column added to trades.")
        else:
            print("ℹ️ 'tenant' column already exists in trades, skipping.")

        # Also check pnl_attribution (if table exists)
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name='pnl_attribution'
            )
        """))
        if result.scalar():
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='pnl_attribution' AND column_name='tenant'
                )
            """))
            if not result.scalar():
                print("Adding 'tenant' column to pnl_attribution table...")
                conn.execute(text("""
                    ALTER TABLE pnl_attribution ADD COLUMN tenant VARCHAR(50) DEFAULT 'default' NOT NULL
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pnl_attribution_tenant ON pnl_attribution (tenant)"))
                print("✅ 'tenant' column added to pnl_attribution.")
            else:
                print("ℹ️ 'tenant' already exists in pnl_attribution, skipping.")

        # Also check collateral_holdings
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name='collateral_holdings'
            )
        """))
        if result.scalar():
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='collateral_holdings' AND column_name='tenant'
                )
            """))
            if not result.scalar():
                print("Adding 'tenant' column to collateral_holdings table...")
                conn.execute(text("""
                    ALTER TABLE collateral_holdings ADD COLUMN tenant VARCHAR(50) DEFAULT 'default' NOT NULL
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_collateral_holdings_tenant ON collateral_holdings (tenant)"))
                print("✅ 'tenant' column added to collateral_holdings.")
            else:
                print("ℹ️ 'tenant' already exists in collateral_holdings, skipping.")

        # Commit all changes
        conn.commit()
        print("✅ All missing columns have been added.")

if __name__ == "__main__":
    add_missing_columns()
