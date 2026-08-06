#!/usr/bin/env python3
"""
Ensure all tenant columns exist and create admin device.
This script is idempotent and safe to run on every startup.
"""

import os
import sys
import sqlalchemy as sa
from sqlalchemy import text
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

# List of tables that need a `tenant` column
TABLES_NEEDING_TENANT = [
    'trades',
    'counterparties',
    'pnl_attribution',
    'collateral_holdings',
    'risk_metrics',
    'execution_orders',
    'users',  # users already has tenant, but we'll check anyway
]

def add_tenant_columns():
    """Add tenant column to all tables that need it."""
    engine = sa.create_engine(Config.DATABASE_URL)
    with engine.connect() as conn:
        for table in TABLES_NEEDING_TENANT:
            # Check if table exists
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = '{table}'
                )
            """))
            if not result.scalar():
                logger.info(f"Table {table} does not exist, skipping.")
                continue

            # Check if tenant column exists
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '{table}'
                      AND column_name = 'tenant'
                )
            """))
            if not result.scalar():
                logger.info(f"Adding tenant column to {table}...")
                # Determine appropriate length
                col_type = "VARCHAR(100)" if table == 'execution_orders' else "VARCHAR(50)"
                conn.execute(text(f"""
                    ALTER TABLE {table}
                    ADD COLUMN tenant {col_type} DEFAULT 'default' NOT NULL
                """))
                # Create index
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant ON {table} (tenant)"))
                logger.info(f"✅ Added tenant column and index to {table}.")
            else:
                logger.info(f"ℹ️ Tenant column already exists on {table}.")

        # ---- Create default admin device ----
        create_default_admin_device(conn)

        conn.commit()
        logger.info("✅ Schema update complete.")


def create_default_admin_device(conn):
    """Create an approved device for the admin user if it doesn't exist."""
    result = conn.execute(text("SELECT id FROM users WHERE email = 'admin@chronos.com'"))
    row = result.fetchone()
    if row:
        admin_id = row[0]
        # Check if device already exists
        result = conn.execute(text("SELECT id FROM devices WHERE user_id = :uid"), {"uid": admin_id})
        if not result.fetchone():
            logger.info("Creating default approved device for admin...")
            conn.execute(text("""
                INSERT INTO devices (id, user_id, device_name, device_fingerprint, status, tenant, requested_at, approved_at)
                VALUES (gen_random_uuid(), :uid, 'Default Web Client', 'web-client', 'approved', 'default', NOW(), NOW())
            """), {"uid": admin_id})
            logger.info("✅ Default device created for admin with fingerprint 'web-client'.")


if __name__ == "__main__":
    add_tenant_columns()
