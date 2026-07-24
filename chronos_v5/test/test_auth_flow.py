# chronos_v5/tests/test_auth_flow.py
import os
import sys
import pytest
from fastapi.testclient import TestClient

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
from unittest.mock import patch

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

    # 3. Approve user
    raw_key = service.approve_user(uuid.UUID(user_id), admin_id)
    assert raw_key is not None

    # 4. Login without fingerprint (should fail)
    resp = client.post("/auth/login", json={
        "email": "test@bank.com",
        "password": "SecurePass123!"
    })
    assert resp.status_code == 422  # validation error because device_fingerprint missing

    # 5. Pair a device
    # First login with JWT (we can't login yet because no device, so we use admin to create device?)
    # Actually we need to create a pairing code – but that requires auth.
    # Since we haven't logged in yet, we'll create a device directly in DB for test
    device = Device(
        user_id=uuid.UUID(user_id),
        device_name="test_device",
        device_fingerprint="test_fingerprint",
        status="approved",
        tenant="default"
    )
    db.add(device)
    db.commit()

    # 6. Login with fingerprint
    resp = client.post("/auth/login", json={
        "email": "test@bank.com",
        "password": "SecurePass123!",
        "device_fingerprint": "test_fingerprint"
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # 7. Access protected endpoint
    resp = client.get("/tenant/savings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # 8. Access with API key
    resp = client.get("/tenant/savings", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200

    # 9. No credentials
    resp = client.get("/tenant/savings")
    assert resp.status_code == 401
