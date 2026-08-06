#!/usr/bin/env python3
"""
Bootstraps the database schema and creates a default admin user + device.
Safe to run on every startup – idempotent.
"""

import sqlalchemy as sa
from sqlalchemy import text
from chronos_v5.config import Config
from chronos_v5.models import Base, User, Device, APIKey
from chronos_v5.logger_setup import logger
import bcrypt
import uuid
from datetime import datetime, timezone

def bootstrap():
    engine = sa.create_engine(Config.DATABASE_URL)
    
    # 1. Create all tables if they don't exist
    Base.metadata.create_all(engine)
    logger.info("✅ Tables ensured (including devices, api_keys, etc.)")

    with engine.connect() as conn:
        # 2. Add tenant column to any table that might be missing it
        tables_needing_tenant = [
            ('trades', 'VARCHAR(50)'),
            ('counterparties', 'VARCHAR(50)'),
            ('pnl_attribution', 'VARCHAR(50)'),
            ('collateral_holdings', 'VARCHAR(50)'),
            ('risk_metrics', 'VARCHAR(50)'),
            ('execution_orders', 'VARCHAR(100)'),
        ]
        for table, col_type in tables_needing_tenant:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant {col_type} DEFAULT 'default' NOT NULL"))
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant ON {table} (tenant)"))
                logger.info(f"✅ Ensured tenant on {table}")
            except Exception as e:
                logger.warning(f"Could not add tenant to {table}: {e}")

        # 3. Ensure admin user exists with known password
        admin_email = "admin@chronos.com"
        admin_password = "Admin123!"  # change if you want, but keep consistent
        hashed = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
        
        # Check if admin exists
        result = conn.execute(text("SELECT id, password_hash FROM users WHERE email = :email"), {"email": admin_email})
        row = result.fetchone()
        if row:
            admin_id = row[0]
            # Update password to ensure it's correct (optional)
            conn.execute(text("UPDATE users SET password_hash = :hash WHERE id = :id"), {"hash": hashed, "id": admin_id})
            logger.info(f"✅ Admin user exists, password updated to '{admin_password}'")
        else:
            # Create admin
            admin_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            conn.execute(
                text("""
                    INSERT INTO users (id, email, password_hash, full_name, status, is_active, role, tenant, created_at)
                    VALUES (:id, :email, :hash, 'System Admin', 'approved', TRUE, 'admin', 'default', :now)
                """),
                {"id": admin_id, "email": admin_email, "hash": hashed, "now": now}
            )
            logger.info(f"✅ Admin user created with email '{admin_email}' and password '{admin_password}'")

        # 4. Create an approved device for the admin (fingerprint = 'web-client')
        # First, check if device already exists
        result = conn.execute(text("SELECT id FROM devices WHERE user_id = :uid AND device_fingerprint = 'web-client'"), {"uid": admin_id})
        if not result.fetchone():
            device_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            conn.execute(
                text("""
                    INSERT INTO devices (id, user_id, device_name, device_fingerprint, status, tenant, requested_at, approved_at)
                    VALUES (:id, :uid, 'Default Web Client', 'web-client', 'approved', 'default', :now, :now)
                """),
                {"id": device_id, "uid": admin_id, "now": now}
            )
            logger.info("✅ Approved device created for admin (fingerprint: 'web-client')")
        else:
            logger.info("ℹ️ Device already exists, skipping.")

        conn.commit()
        logger.info("🎉 Bootstrap complete. You can now login with admin@chronos.com / Admin123!")

if __name__ == "__main__":
    bootstrap()
