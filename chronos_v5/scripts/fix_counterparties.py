import sqlalchemy as sa
from sqlalchemy import text
from chronos_v5.config import Config

def fix():
    engine = sa.create_engine(Config.DATABASE_URL)
    with engine.connect() as conn:
        # 1. Add tenant column (already done, but safe to re-run)
        conn.execute(text("ALTER TABLE counterparties ADD COLUMN IF NOT EXISTS tenant VARCHAR(50) DEFAULT 'default' NOT NULL"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_counterparties_tenant ON counterparties (tenant)"))

        # 2. Create a default approved device for admin
        conn.execute(text("""
            INSERT INTO devices (id, user_id, device_name, device_fingerprint, status, tenant, requested_at, approved_at)
            SELECT gen_random_uuid(), u.id, 'Default Web Client', 'web-client', 'approved', 'default', NOW(), NOW()
            FROM users u
            WHERE u.email = 'admin@chronos.com'
            ON CONFLICT DO NOTHING
        """))

        # 3. Ensure admin password is set to a known value (optional)
        # Uncomment if you want to force password to 'Admin123!'
        # conn.execute(text("UPDATE users SET password_hash = crypt('Admin123!', gen_salt('bf')) WHERE email = 'admin@chronos.com'"))

        conn.commit()
        print("✅ Fixed counterparties.tenant and created admin device")

if __name__ == "__main__":
    fix()
