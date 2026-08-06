#!/usr/bin/env python3
"""
Ensure all required columns exist – including `tenant` on every table.
Uses `ADD COLUMN IF NOT EXISTS` – idempotent and safe.
"""

import os
import sys
import sqlalchemy as sa
from sqlalchemy import text
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

def add_tenant_columns():
    engine = sa.create_engine(Config.DATABASE_URL)
    with engine.connect() as conn:
        # List of (table, column_type)
        tables = [
            ('trades', 'VARCHAR(50)'),
            ('counterparties', 'VARCHAR(50)'),
            ('pnl_attribution', 'VARCHAR(50)'),
            ('collateral_holdings', 'VARCHAR(50)'),
            ('risk_metrics', 'VARCHAR(50)'),
            ('execution_orders', 'VARCHAR(100)'),
        ]
        for table, col_type in tables:
            try:
                conn.execute(text(f"""
                    ALTER TABLE {table}
                    ADD COLUMN IF NOT EXISTS tenant {col_type} DEFAULT 'default' NOT NULL
                """))
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant ON {table} (tenant)"))
                logger.info(f"✅ Ensured tenant column on {table}")
            except Exception as e:
                logger.warning(f"Could not add tenant to {table}: {e}")

        # Default admin device
        result = conn.execute(text("SELECT id FROM users WHERE email = 'admin@chronos.com'"))
        row = result.fetchone()
        if row:
            admin_id = row[0]
            conn.execute(text("""
                INSERT INTO devices (id, user_id, device_name, device_fingerprint, status, tenant, requested_at, approved_at)
                VALUES (gen_random_uuid(), :uid, 'Default Web Client', 'web-client', 'approved', 'default', NOW(), NOW())
                ON CONFLICT DO NOTHING
            """), {"uid": admin_id})
            logger.info("✅ Default admin device ensured.")

        conn.commit()
        logger.info("✅ Schema sync complete.")

if __name__ == "__main__":
    add_tenant_columns()
