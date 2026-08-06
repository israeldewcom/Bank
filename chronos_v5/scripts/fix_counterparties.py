import sqlalchemy as sa
from sqlalchemy import text, Table, Column, String, UUID, Boolean, DateTime, ForeignKey
from chronos_v5.config import Config
from chronos_v5.models import Base, Device

def fix():
    engine = sa.create_engine(Config.DATABASE_URL)
    
    # Create all missing tables (including devices)
    Base.metadata.create_all(engine)
    print("✅ Ensured all tables exist (including devices)")

    with engine.connect() as conn:
        # Ensure tenant column on counterparties
        conn.execute(text("ALTER TABLE counterparties ADD COLUMN IF NOT EXISTS tenant VARCHAR(50) DEFAULT 'default' NOT NULL"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_counterparties_tenant ON counterparties (tenant)"))

        # Insert default admin device
        conn.execute(text("""
            INSERT INTO devices (id, user_id, device_name, device_fingerprint, status, tenant, requested_at, approved_at)
            SELECT gen_random_uuid(), u.id, 'Default Web Client', 'web-client', 'approved', 'default', NOW(), NOW()
            FROM users u
            WHERE u.email = 'admin@chronos.com'
            ON CONFLICT (id) DO NOTHING
        """))

        conn.commit()
        print("✅ Fixed counterparties.tenant and created admin device")

if __name__ == "__main__":
    fix()
