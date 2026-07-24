# chronos_v5/tests/test_auth_flow.py
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# ---- CRITICAL: Override config BEFORE importing app ----
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["CHRONOS_ENV"] = "test"
os.environ["CHRONOS_API_KEY"] = "test-key"
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-chars-long"
os.environ["ASYNC_DB"] = "false"

from chronos_v5.api.app import app
from chronos_v5.database import sync_engine, SyncSessionLocal
from chronos_v5.models import Base, User, Device
from chronos_v5.config import Config
from chronos_v5.services.auth_service import AuthService
import uuid

Config.validate()

@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(sync_engine)
    with patch("chronos_v5.services.tenant_config_service.redis.from_url") as mock_redis:
        mock_redis.return_value = None
        with TestClient(app) as c:
            yield c
    Base.metadata.drop_all(sync_engine)

def test_auth_flow(client):
    # 1. Register
    resp = client.post("/auth/register", json={
        "email": "test@bank.com",
        "password": "SecurePass123!",
        "full_name": "Test User"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    user_id = data["user_id"]

    # 2. Create admin
    db = SyncSessionLocal()
    service = AuthService()
    admin = User(
        email="admin@chronos.local",
        hashed_password=service.hash_password("Admin123!"),
        full_name="Admin",
        status="approved",
        role="admin",
        tenant="default"
    )
    db.add(admin)
    db.commit()
    admin_id = admin.id

    # 3. Approve user → API key generated
    raw_key = service.approve_user(uuid.UUID(user_id), admin_id)
    assert raw_key is not None

    # 4. Login without fingerprint → validation error
    resp = client.post("/auth/login", json={
        "email": "test@bank.com",
        "password": "SecurePass123!"
    })
    assert resp.status_code == 422

    # 5. Use API key to request pairing code
    resp = client.post(
        "/auth/pairing-code?device_name=test_device",
        headers={"X-API-Key": raw_key}
    )
    assert resp.status_code == 200
    code = resp.json()["pairing_code"]

    # 6. Pair device
    resp = client.post("/auth/pair-device", json={
        "email": "test@bank.com",
        "pairing_code": code,
        "device_name": "test_device",
        "device_fingerprint": "test_fingerprint"
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"

    # 7. Admin approves device
    device = db.query(Device).filter(Device.user_id == uuid.UUID(user_id)).first()
    service.approve_device(device.id, admin_id)

    # 8. Login with fingerprint
    resp = client.post("/auth/login", json={
        "email": "test@bank.com",
        "password": "SecurePass123!",
        "device_fingerprint": "test_fingerprint"
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # 9. Access protected endpoint with JWT
    resp = client.get("/tenant/savings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # 10. Access with API key
    resp = client.get("/tenant/savings", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200

    # 11. No credentials → 401
    resp = client.get("/tenant/savings")
    assert resp.status_code == 401

    # 12. Unpaired fingerprint → 401 with clear message
    resp = client.post("/auth/login", json={
        "email": "test@bank.com",
        "password": "SecurePass123!",
        "device_fingerprint": "unknown"
    })
    assert resp.status_code == 401
    assert "device" in resp.json()["detail"].lower()
