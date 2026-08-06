#!/usr/bin/env python3
"""
Synchronise the database schema with SQLAlchemy models.
Adds any missing columns, indexes, and creates a default admin device.
Idempotent – safe to run multiple times.
"""

import os
import sys
import sqlalchemy as sa
from sqlalchemy import text, inspect
from sqlalchemy.engine.reflection import Inspector
from chronos_v5.config import Config
from chronos_v5.models import Base, User, Trade, Counterparty, PnLAttribution, CollateralHolding, RiskMetrics, ExecutionOrder, APIKey, Device
from chronos_v5.logger_setup import logger

# Map SQLAlchemy types to PostgreSQL column definitions
TYPE_MAP = {
    sa.String: lambda col: f"VARCHAR({col.length})" if col.length else "VARCHAR",
    sa.Integer: lambda col: "INTEGER",
    sa.BigInteger: lambda col: "BIGINT",
    sa.Float: lambda col: "FLOAT",
    sa.Boolean: lambda col: "BOOLEAN",
    sa.DateTime: lambda col: "TIMESTAMP",
    sa.JSON: lambda col: "JSON",
    sa.Text: lambda col: "TEXT",
    sa.Enum: lambda col: f"VARCHAR(20)",  # simplified; enums are handled separately if needed
}

def get_column_definition(col):
    """Return a SQL string for the column definition."""
    col_type = type(col.type)
    type_def = TYPE_MAP.get(col_type)
    if type_def is None:
        # Fallback: use the string representation
        return str(col.type)
    return type_def(col.type)

def get_default_value(col):
    """Return a SQL default string if the column has a server_default or default."""
    if col.server_default is not None:
        return f"DEFAULT {col.server_default.arg}"
    if col.default is not None:
        # For Python defaults, we can't easily translate; we'll just omit
        # and let the application handle it, or set a default in the ADD COLUMN
        # For common columns, we can hardcode defaults.
        return None
    return None

def add_missing_columns():
    """Add missing columns to all tables based on models."""
    engine = sa.create_engine(Config.DATABASE_URL)
    inspector = Inspector.from_engine(engine)
    metadata = Base.metadata

    with engine.connect() as conn:
        # Iterate over all tables defined in models
        for table_name, table in metadata.tables.items():
            # Skip if table doesn't exist in DB
            if not inspector.has_table(table_name):
                logger.info(f"Table {table_name} does not exist; will create later via Alembic or create_all.")
                continue

            # Get existing columns
            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
            # Get columns from the model
            model_columns = {col.name: col for col in table.columns}

            for col_name, col in model_columns.items():
                if col_name not in existing_columns:
                    # Build ALTER TABLE statement
                    col_def = get_column_definition(col)
                    default = get_default_value(col)
                    nullable = "NOT NULL" if not col.nullable else ""
                    # Add default if not nullable but no default provided? Use a safe default.
                    if not col.nullable and default is None:
                        # For non-nullable columns without server_default, we need to add a default
                        # or allow NULL temporarily then set a default.
                        if col_name == 'tenant':
                            default = "DEFAULT 'default'"
                        elif col_name == 'status':
                            default = "DEFAULT 'pending'"
                        elif col_name == 'is_active':
                            default = "DEFAULT FALSE"
                        elif col_name == 'client_order_id':
                            default = "DEFAULT ''"
                        # For others, we may need to decide; we'll set a generic default if possible
                        else:
                            default = "DEFAULT NULL"  # will fail if NOT NULL; we'll alter later
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"
                    if default:
                        sql += f" {default}"
                    if not col.nullable and default is None:
                        # If we can't provide a default, we add as nullable first, then update, then set NOT NULL
                        sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def} NULL"
                        logger.info(f"Adding column {col_name} to {table_name} as nullable (no default)")
                        conn.execute(text(sql))
                        # Then set a default and update existing rows
                        if col_name == 'tenant':
                            conn.execute(text(f"UPDATE {table_name} SET {col_name} = 'default' WHERE {col_name} IS NULL"))
                            conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN {col_name} SET NOT NULL"))
                        elif col_name == 'status':
                            conn.execute(text(f"UPDATE {table_name} SET {col_name} = 'pending' WHERE {col_name} IS NULL"))
                            conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN {col_name} SET NOT NULL"))
                        elif col_name == 'is_active':
                            conn.execute(text(f"UPDATE {table_name} SET {col_name} = FALSE WHERE {col_name} IS NULL"))
                            conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN {col_name} SET NOT NULL"))
                        elif col_name == 'client_order_id':
                            conn.execute(text(f"UPDATE {table_name} SET {col_name} = '' WHERE {col_name} IS NULL"))
                            conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN {col_name} SET NOT NULL"))
                        else:
                            # For other columns, just leave as nullable to avoid errors
                            pass
                        logger.info(f"✅ Added column {col_name} to {table_name} and set NOT NULL")
                    else:
                        conn.execute(text(sql))
                        logger.info(f"✅ Added column {col_name} to {table_name}")

            # Create indexes for tenant and status columns
            if 'tenant' in model_columns and 'tenant' not in existing_columns:
                # Index might already exist; try to create
                try:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table_name}_tenant ON {table_name} (tenant)"))
                    logger.info(f"✅ Created index on tenant for {table_name}")
                except Exception as e:
                    logger.warning(f"Could not create index on tenant for {table_name}: {e}")
            if 'status' in model_columns and 'status' not in existing_columns:
                try:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table_name}_status ON {table_name} (status)"))
                    logger.info(f"✅ Created index on status for {table_name}")
                except Exception as e:
                    logger.warning(f"Could not create index on status for {table_name}: {e}")

        # ---- Create default admin device ----
        create_default_admin_device(conn)

        conn.commit()
        logger.info("✅ Schema synchronisation complete.")


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
    add_missing_columns()
