import sqlalchemy as sa
from sqlalchemy import text
from chronos_v5.config import Config

def fix():
    engine = sa.create_engine(Config.DATABASE_URL)
    with engine.connect() as conn:
        # 1. Ensure tenant column exists (already done, but safe)
        conn.execute(text("ALTER TABLE counterparties ADD COLUMN IF NOT EXISTS tenant VARCHAR(50) DEFAULT 'default' NOT NULL"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_counterparties_tenant ON counterparties (tenant)"))

        # 2. Create approved device for admin (THIS IS CRITICAL)
        conn.execute(text("""
            INSERT INTO devices (id, user_id, device_name, device_fingerprint, status, tenant, requested_at, approved_at)
            SELECT gen_random_uuid(), u.id, 'Default Web Client', 'web-client', 'approved', 'default', NOW(), NOW()
            FROM users u
            WHERE u.email = 'admin@chronos.com'
            ON CONFLICT (id) DO NOTHING
        """))

        # 3. Ensure admin password is 'Admin123!'
        # (If you want a different password, change the string here)
        conn.execute(text("UPDATE users SET password_hash = crypt('Admin123!', gen_salt('bf')) WHERE email = 'admin@chronos.com'"))

        conn.commit()
        print("✅ Fixed columns and created admin device with password 'Admin123!'")

if __name__ == "__main__":
    fix()
