#!/usr/bin/env python3
"""
Synchronise database schema with SQLAlchemy models.
Adds missing columns, indexes, and creates a default admin device.
Idempotent and safe to run on every startup.
"""

import os
import sys
import sqlalchemy as sa
from sqlalchemy import text, inspect
from sqlalchemy.engine.reflection import Inspector
from chronos_v5.config import Config
from chronos_v5.models import Base
from chronos_v5.logger_setup import logger

# Map SQLAlchemy types to PostgreSQL DDL strings
TYPE_MAP = {
    sa.String: lambda col: f"VARCHAR({col.length})" if col.length else "VARCHAR",
    sa.Integer: lambda col: "INTEGER",
    sa.BigInteger: lambda col: "BIGINT",
    sa.Float: lambda col: "FLOAT",
    sa.Boolean: lambda col: "BOOLEAN",
    sa.DateTime: lambda col: "TIMESTAMP",
    sa.JSON: lambda col: "JSON",
    sa.Text: lambda col: "TEXT",
    sa.Enum: lambda col: "VARCHAR(20)",  # simplified
}

def get_column_definition(col):
    """Return a SQL string for the column definition."""
    col_type = type(col.type)
    type_def = TYPE_MAP.get(col_type)
    if type_def is None:
        # Fallback: use the string representation
        return str(col.type)
    return type_def(col.type)

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
                logger.info(f"Table {table_name} does not exist; skipping column checks.")
                continue

            # Get existing columns
            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
            # Get columns from the model
            model_columns = {col.name: col for col in table.columns}

            for col_name, col in model_columns.items():
                if col_name not in existing_columns:
                    # Build ALTER TABLE statement
                    col_def = get_column_definition(col)
                    nullable = "NOT NULL" if not col.nullable else ""
                    # Determine default value
                    default = None
                    if col.server_default is not None:
                        default = f"DEFAULT {col.server_default.arg}"
                    elif not col.nullable:
                        # Provide sensible defaults for known columns
                        if col_name == 'tenant':
                            default = "DEFAULT 'default'"
                        elif col_name == 'status':
                            default = "DEFAULT 'pending'"
                        elif col_name == 'is_active':
                            default = "DEFAULT FALSE"
                        elif col_name == 'client_order_id':
                            default = "DEFAULT ''"
                        elif col_name == 'id':
                            default = "DEFAULT gen_random_uuid()"
                        else:
                            # For other columns, we'll add as nullable first, then set default later
                            pass

                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"
                    if default:
                        sql += f" {default}"
                    if not col.nullable and default is None:
                        # Add as nullable first, then update and set NOT NULL
                        logger.info(f"Adding {col_name} to {table_name} as nullable (will set default and NOT NULL later)")
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def} NULL"))
                        # Set a default value for existing rows
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
                            # For other columns, leave as nullable
                            pass
                        logger.info(f"✅ Added column {col_name} to {table_name} with NOT NULL")
                    else:
                        conn.execute(text(sql))
                        logger.info(f"✅ Added column {col_name} to {table_name}")

            # Create indexes for tenant and status columns
            if 'tenant' in model_columns:
                try:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table_name}_tenant ON {table_name} (tenant)"))
                    logger.info(f"✅ Created index on tenant for {table_name}")
                except Exception as e:
                    logger.warning(f"Could not create index on tenant for {table_name}: {e}")
            if 'status' in model_columns:
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
