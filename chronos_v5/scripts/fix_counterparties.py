import os
import sqlalchemy as sa
from sqlalchemy import text
from chronos_v5.config import Config

engine = sa.create_engine(Config.DATABASE_URL)
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE counterparties ADD COLUMN IF NOT EXISTS tenant VARCHAR(50) DEFAULT 'default' NOT NULL"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_counterparties_tenant ON counterparties (tenant)"))
    conn.commit()
    print("✅ Fixed counterparties.tenant")
