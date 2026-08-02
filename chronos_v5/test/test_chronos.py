# chronos_v5/test/test_chronos.py
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["CHRONOS_ENV"] = "test"
os.environ["CHRONOS_API_KEY"] = "test-key"
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-chars-long"
os.environ["ASYNC_DB"] = "false"

from chronos_v5.api.app import app
from chronos_v5.database import sync_engine, SyncSessionLocal
from chronos_v5.models import Base, User, Device
from chronos_v5.services.auth_service import AuthService
from chronos_v5.config import Config

Config.validate()

TEST_DEVICE_FINGERPRINT = "test-fixture-device-fp-001"


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(sync_engine)
    with patch("chronos_v5.services.tenant_config_service.redis.from_url") as mock_redis:
        mock_redis.return_value = None
        with TestClient(app) as c:
            yield c
    Base.metadata.drop_all(sync_engine)


@pytest.fixture(scope="module")
def auth_headers(client):
    db = SyncSessionLocal()
    service = AuthService()
    user = User(
        id=str(uuid.uuid4()),
        email="trader@bank.com",
        password_hash=service.hash_password("SecurePass123!"),
        full_name="Test Trader",
        status="approved",
        is_active=True,
        role="trader",
        tenant="default",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    device = Device(
        id=str(uuid.uuid4()),
        user_id=user.id,
        device_name="test-fixture-device",
        device_fingerprint=TEST_DEVICE_FINGERPRINT,
        status="approved",
        tenant="default",
    )
    db.add(device)
    db.commit()
    db.close()

    resp = client.post("/auth/login", json={
        "email": "trader@bank.com",
        "password": "SecurePass123!",
        "device_fingerprint": TEST_DEVICE_FINGERPRINT,
    })
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _trade_payload(trade_id, idempotency_key):
    return {
        "id": trade_id,
        "desk": "FX",
        "counterparty_id": "CP-001",
        "instrument_type": "FX_SPOT",
        "currency": "NGN",
        "notional": 500000,
        "settle_date": "2099-01-01T00:00:00",
        "idempotency_key": idempotency_key,
    }


def test_ingest_trade_returns_prediction(client, auth_headers):
    resp = client.post(
        "/trade/ingest_sync",
        json=_trade_payload("TRADE-001", "idem-key-001"),
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "INGESTED"
    assert body["trade_id"] == "TRADE-001"
    assert 0.0 <= body["fail_probability"] <= 1.0
    assert body["recommended_action"] in ("AUTO_BORROW", "STANDARD")


def test_duplicate_idempotency_key_is_rejected(client, auth_headers):
    first = client.post(
        "/trade/ingest_sync",
        json=_trade_payload("TRADE-002", "idem-key-002"),
        headers=auth_headers,
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/trade/ingest_sync",
        json=_trade_payload("TRADE-003", "idem-key-002"),
        headers=auth_headers,
    )
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "DUPLICATE"


def test_get_trade_requires_auth(client):
    resp = client.get("/trade/TRADE-001")
    assert resp.status_code in (401, 403)


def test_get_nonexistent_trade_returns_404(client, auth_headers):
    resp = client.get("/trade/DOES-NOT-EXIST", headers=auth_headers)
    assert resp.status_code == 404
