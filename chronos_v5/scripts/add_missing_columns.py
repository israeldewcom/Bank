# chronos_v5/scripts/add_missing_columns.py
import os
import sqlalchemy as sa
from sqlalchemy import text
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

def add_missing_columns():
    """Add missing columns to users, trades, and other tables if they don't exist."""
    engine = sa.create_engine(Config.DATABASE_URL)
    with engine.connect() as conn:
        # ---- USERS ----
        # status column
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='status'
            )
        """))
        if not result.scalar():
            print("Adding 'status' to users...")
            conn.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(20) DEFAULT 'pending' NOT NULL"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_status ON users (status)"))
        # is_active column
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='is_active'
            )
        """))
        if not result.scalar():
            print("Adding 'is_active' to users...")
            conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT FALSE"))
        # Ensure no NULLs
        conn.execute(text("UPDATE users SET status = 'pending' WHERE status IS NULL"))
        conn.execute(text("UPDATE users SET is_active = FALSE WHERE is_active IS NULL"))

        # ---- TRADES ----
        # Check and add all missing columns based on models.py
        columns_to_check = {
            'tenant': 'VARCHAR(50) DEFAULT \'default\' NOT NULL',
            'nibss_ref': 'VARCHAR(100)',
            'settled_at': 'TIMESTAMP',
            'encrypted_counterparty': 'TEXT',
            'price_quote': 'JSON',
            'fail_probability': 'FLOAT DEFAULT 0.0',
        }
        for col, col_def in columns_to_check.items():
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='trades' AND column_name='{col}'
                )
            """))
            if not result.scalar():
                print(f"Adding '{col}' to trades...")
                conn.execute(text(f"ALTER TABLE trades ADD COLUMN {col} {col_def}"))
                if col in ['tenant', 'nibss_ref']:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_trades_{col} ON trades ({col})"))
                print(f"✅ '{col}' added to trades.")
            else:
                print(f"ℹ️ '{col}' already exists in trades, skipping.")

        # ---- PNL_ATTRIBUTION ----
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
                print("Adding 'tenant' to pnl_attribution...")
                conn.execute(text("ALTER TABLE pnl_attribution ADD COLUMN tenant VARCHAR(50) DEFAULT 'default' NOT NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pnl_attribution_tenant ON pnl_attribution (tenant)"))

        # ---- COLLATERAL_HOLDINGS ----
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
                print("Adding 'tenant' to collateral_holdings...")
                conn.execute(text("ALTER TABLE collateral_holdings ADD COLUMN tenant VARCHAR(50) DEFAULT 'default' NOT NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_collateral_holdings_tenant ON collateral_holdings (tenant)"))

        # ---- RISK_METRICS ----
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name='risk_metrics'
            )
        """))
        if result.scalar():
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='risk_metrics' AND column_name='tenant'
                )
            """))
            if not result.scalar():
                print("Adding 'tenant' to risk_metrics...")
                conn.execute(text("ALTER TABLE risk_metrics ADD COLUMN tenant VARCHAR(50) DEFAULT 'default' NOT NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_risk_metrics_tenant ON risk_metrics (tenant)"))

        # ---- EXECUTION_ORDERS ----
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name='execution_orders'
            )
        """))
        if result.scalar():
            # tenant
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='execution_orders' AND column_name='tenant'
                )
            """))
            if not result.scalar():
                print("Adding 'tenant' to execution_orders...")
                conn.execute(text("ALTER TABLE execution_orders ADD COLUMN tenant VARCHAR(100) DEFAULT 'default' NOT NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_execution_orders_tenant ON execution_orders (tenant)"))
            # client_order_id
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='execution_orders' AND column_name='client_order_id'
                )
            """))
            if not result.scalar():
                print("Adding 'client_order_id' to execution_orders...")
                conn.execute(text("ALTER TABLE execution_orders ADD COLUMN client_order_id VARCHAR(64) DEFAULT '' NOT NULL"))
                # Also add unique constraint if not exists
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_orders_client_order_id ON execution_orders (client_order_id)"))
            # gateway_response
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='execution_orders' AND column_name='gateway_response'
                )
            """))
            if not result.scalar():
                print("Adding 'gateway_response' to execution_orders...")
                conn.execute(text("ALTER TABLE execution_orders ADD COLUMN gateway_response JSON"))

        # Commit all changes
        conn.commit()
        print("✅ All missing columns have been added.")


def fix_missing_columns_in_trades():
    """Specifically add nibss_ref and settled_at to trades if missing."""
    engine = sa.create_engine(Config.DATABASE_URL)
    with engine.connect() as conn:
        # Check nibss_ref
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='trades' AND column_name='nibss_ref'
            )
        """))
        if not result.scalar():
            print("Adding 'nibss_ref' to trades...")
            conn.execute(text("ALTER TABLE trades ADD COLUMN nibss_ref VARCHAR(100)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_trades_nibss_ref ON trades (nibss_ref)"))
            print("✅ 'nibss_ref' added.")
        else:
            print("ℹ️ 'nibss_ref' already exists, skipping.")

        # Check settled_at
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='trades' AND column_name='settled_at'
            )
        """))
        if not result.scalar():
            print("Adding 'settled_at' to trades...")
            conn.execute(text("ALTER TABLE trades ADD COLUMN settled_at TIMESTAMP"))
            print("✅ 'settled_at' added.")
        else:
            print("ℹ️ 'settled_at' already exists, skipping.")

        conn.commit()


if __name__ == "__main__":
    # First run the comprehensive fix
    add_missing_columns()
    # Then specifically ensure nibss_ref and settled_at (in case the comprehensive missed)
    fix_missing_columns_in_trades()
