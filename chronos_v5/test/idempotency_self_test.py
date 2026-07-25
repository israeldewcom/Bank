# chronos_v5/tests/idempotency_self_test.py
import asyncio
import httpx
import uuid
import bcrypt
import secrets
import os
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User, APIKey
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

async def run_idempotency_self_test(base_url: str = None):
    """
    Runs 50 concurrent POST requests with the same idempotency_key.
    Asserts exactly 1 trade is created.
    Logs the result (PASS/FAIL) and returns a boolean.
    """
    if base_url is None:
        port = os.getenv("PORT", "10000")
        base_url = f"http://localhost:{port}"

    # 1. Create a temporary test user and API key directly in DB
    db = SyncSessionLocal()
    test_email = f"self_test_{uuid.uuid4().hex[:8]}@chronos.local"
    test_user = User(
        id=uuid.uuid4(),
        email=test_email,
        hashed_password=bcrypt.hashpw(b"temp_pass", bcrypt.gensalt()).decode(),
        full_name="Self Test",
        status="approved",
        role="user",
        tenant="default"
    )
    db.add(test_user)
    db.commit()
    raw_key = secrets.token_urlsafe(32)
    api_key = APIKey(
        user_id=test_user.id,
        key_prefix=raw_key[:12],
        key_hash=bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode(),
        tenant="default"
    )
    db.add(api_key)
    db.commit()
    db.close()

    logger.info(f"Self‑test: created temporary user {test_email} with API key")

    async def send_trade(client, idempotency_key):
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
            headers={"X-API-Key": raw_key, "X-Tenant": "default"}
        )
        return resp.status_code, resp.json()

    idempotency_key = f"self_test_{uuid.uuid4().hex}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [send_trade(client, idempotency_key) for _ in range(50)]
        results = await asyncio.gather(*tasks)

    successes = [r[1] for r in results if r[0] == 200]
    ingested = [r[1] for r in successes if r[1].get("status") == "INGESTED"]
    duplicates = [r[1] for r in successes if r[1].get("status") == "DUPLICATE"]

    passed = len(ingested) == 1 and len(duplicates) == 49
    logger.info(f"Self‑test: {len(ingested)} INGESTED, {len(duplicates)} DUPLICATE → {'PASS' if passed else 'FAIL'}")
    return passed
