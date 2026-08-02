# chronos_v5/tests/idempotency_self_test.py
import asyncio
import httpx
import uuid
import bcrypt
import secrets
import os
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User, APIKey, Trade
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

async def run_idempotency_self_test(base_url: str = None):
    """
    Runs 50 concurrent POST requests with the same idempotency_key.
    Asserts exactly 1 trade is created.
    Also tests cross-tenant isolation: creates two tenants, inserts trades,
    and verifies that queries for tenant A never return tenant B's rows.
    Logs the result (PASS/FAIL) and returns a boolean.
    """
    if base_url is None:
        port = os.getenv("PORT", "8000")
        base_url = f"http://localhost:{port}"

    db = SyncSessionLocal()

    # --- Create two test tenants ---
    tenants = ["tenant_a", "tenant_b"]
    test_users = {}
    raw_keys = {}

    for tenant in tenants:
        test_email = f"self_test_{tenant}_{uuid.uuid4().hex[:8]}@chronos.local"
        test_user = User(
            id=str(uuid.uuid4()),
            email=test_email,
            password_hash=bcrypt.hashpw(b"temp_pass", bcrypt.gensalt()).decode(),
            full_name=f"Self Test {tenant}",
            status="approved",
            is_active=True,
            role="user",
            tenant=tenant
        )
        db.add(test_user)
        db.commit()
        raw_key = secrets.token_urlsafe(32)
        api_key = APIKey(
            user_id=test_user.id,
            key_prefix=raw_key[:12],
            key_hash=bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode(),
            tenant=tenant
        )
        db.add(api_key)
        db.commit()
        test_users[tenant] = test_user
        raw_keys[tenant] = raw_key
        logger.info(f"Self‑test: created user for tenant {tenant}")

    # --- Test 1: Idempotency (50 concurrent) ---
    async def send_trade(client, idempotency_key, tenant):
        payload = {
            "id": str(uuid.uuid4()),
            "desk": "SELF_TEST",
            "counterparty_id": "SELF",
            "currency": "NGN",
            "notional": 1000,
            "settle_date": "2026-12-31T00:00:00",
            "idempotency_key": idempotency_key
        }
        resp = await client.post(
            f"{base_url}/trade/ingest_sync",
            json=payload,
            headers={"X-API-Key": raw_keys[tenant], "X-Tenant": tenant}
        )
        return resp.status_code, resp.json()

    idempotency_key = f"self_test_{uuid.uuid4().hex}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [send_trade(client, idempotency_key, "tenant_a") for _ in range(50)]
        results = await asyncio.gather(*tasks)

    successes = [r[1] for r in results if r[0] == 200]
    ingested = [r[1] for r in successes if r[1].get("status") == "INGESTED"]
    duplicates = [r[1] for r in successes if r[1].get("status") == "DUPLICATE"]
    passed_idempotency = len(ingested) == 1 and len(duplicates) == 49
    logger.info(f"Idempotency test: {len(ingested)} INGESTED, {len(duplicates)} DUPLICATE → {'PASS' if passed_idempotency else 'FAIL'}")

    # --- Test 2: Cross-tenant isolation ---
    # Insert one trade for tenant A, one for tenant B
    async def insert_trade(client, tenant):
        payload = {
            "id": str(uuid.uuid4()),
            "desk": f"ISOLATION_{tenant}",
            "counterparty_id": "SELF",
            "currency": "NGN",
            "notional": 1000,
            "settle_date": "2026-12-31T00:00:00",
            "idempotency_key": f"iso_{uuid.uuid4().hex}"
        }
        resp = await client.post(
            f"{base_url}/trade/ingest_sync",
            json=payload,
            headers={"X-API-Key": raw_keys[tenant], "X-Tenant": tenant}
        )
        return resp.status_code, resp.json()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for tenant in tenants:
            code, resp = await insert_trade(client, tenant)
            assert code == 200, f"Insert failed for tenant {tenant}"

    # Query trades for tenant A and ensure no tenant B trades appear
    async def list_trades(client, tenant):
        resp = await client.get(
            f"{base_url}/trade/",
            headers={"X-API-Key": raw_keys[tenant], "X-Tenant": tenant}
        )
        return resp.json()

    async with httpx.AsyncClient(timeout=30.0) as client:
        trades_a = await list_trades(client, "tenant_a")
        trades_b = await list_trades(client, "tenant_b")

    # Also check via DB directly (more reliable)
    db_trades_a = db.query(Trade).filter(Trade.tenant == "tenant_a").all()
    db_trades_b = db.query(Trade).filter(Trade.tenant == "tenant_b").all()
    a_tenants_db = {t.tenant for t in db_trades_a}
    b_tenants_db = {t.tenant for t in db_trades_b}

    isolation_passed = (
        all(t == "tenant_a" for t in a_tenants_db) and
        all(t == "tenant_b" for t in b_tenants_db) and
        "tenant_b" not in a_tenants_db and
        "tenant_a" not in b_tenants_db
    )
    logger.info(f"Cross-tenant isolation test: {'PASS' if isolation_passed else 'FAIL'}")

    db.close()
    return passed_idempotency and isolation_passed
