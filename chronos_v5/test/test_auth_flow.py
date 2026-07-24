# chronos_v5/tests/test_auth_flow.py
import pytest
from fastapi.testclient import TestClient
from chronos_v5.api.app import app
from chronos_v5.database import sync_engine, SyncSessionLocal
from chronos_v5.models import Base, User, Device
from chronos_v5.config import Config
from chronos_v5.services.auth_service import AuthService
import uuid
from datetime import datetime, timezone

@pytest.fixture(scope="module")
def client():
    # Use test database
    original_url = Config.DATABASE_URL
    Config.DATABASE_URL = "sqlite:///:memory:"
    Base.metadata.create_all(sync_engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(sync_engine)
    Config.DATABASE_URL = original_url

def test_auth_flow(client):
    # 1. Register
    resp = client.post("/auth/register", json={
        "email": "test@bank.com",
        "password": "secure123",
        "full_name": "Test User"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    user_id = data["user_id"]

    # 2. Admin approves (we need to create an admin first – we'll do that via script)
    # For test, we'll directly update DB
    db = SyncSessionLocal()
    service = AuthService()
    admin = User(
        email="admin@chronos.local",
        hashed_password=service.hash_password("admin123"),
        full_name="Admin",
        status="approved",
        role="admin",
        tenant="default"
    )
    db.add(admin)
    db.commit()
    admin_id = admin.id

    # Approve user
    raw_key = service.approve_user(uuid.UUID(user_id), admin_id)
    assert raw_key is not None

    # 3. Login with JWT
    resp = client.post("/auth/login", json={
        "email": "test@bank.com",
        "password": "secure123"
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # 4. Use JWT to access a protected endpoint (e.g., /tenant/savings)
    resp = client.get("/tenant/savings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # 5. Use API Key to access the same endpoint (legacy header)
    resp = client.get("/tenant/savings", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200

    # 6. Device pairing flow
    # Request pairing code (authenticated)
    resp = client.post("/auth/pairing-code?device_name=laptop", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    code = resp.json()["pairing_code"]

    # Pair device (new device, unauthenticated)
    resp = client.post("/auth/pair-device", json={
        "email": "test@bank.com",
        "pairing_code": code,
        "device_name": "new-laptop",
        "device_fingerprint": "fingerprint_hash_123"
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"

    # Admin approves device
    device = db.query(Device).filter(Device.user_id == uuid.UUID(user_id)).first()
    service.approve_device(device.id, admin_id)

    # Now login with device fingerprint (should succeed)
    resp = client.post("/auth/login", json={
        "email": "test@bank.com",
        "password": "secure123",
        "device_fingerprint": "fingerprint_hash_123"
    })
    assert resp.status_code == 200
