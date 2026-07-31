# chronos_v5/api/routers/admin.py
# SECURITY FIX: get_admin_user only ever checked role, never tenant. That
# meant a tenant-A admin could approve/reject users, approve/revoke devices,
# and revoke API keys belonging to ANY tenant, including generating a live
# API key for a tenant-B account and receiving the raw key in the response.
# Every list endpoint below is now filtered to admin.tenant, and every
# action endpoint looks the target up first, then calls require_same_tenant
# before doing anything to it.
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
import uuid
from datetime import datetime, timezone
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User, Device, APIKey
from chronos_v5.services.auth_service import AuthService
from chronos_v5.api.dependencies import get_admin_user, get_current_user, require_same_tenant
from chronos_v5.logger_setup import logger

router = APIRouter()

class ApproveRequest(BaseModel):
    user_id: str

class DeviceActionRequest(BaseModel):
    device_id: str

@router.get("/users/pending")
def list_pending_users(admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        users = db.query(User).filter(User.status == "pending", User.tenant == admin.tenant).all()
        return [{"id": str(u.id), "email": u.email, "full_name": u.full_name, "tenant": u.tenant, "created_at": u.created_at} for u in users]
    finally:
        db.close()

@router.post("/users/approve")
def approve_user(req: ApproveRequest, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        target = db.query(User).filter(User.id == uuid.UUID(req.user_id)).first()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        require_same_tenant(target.tenant, admin)
    finally:
        db.close()

    service = AuthService()
    try:
        raw_key = service.approve_user(uuid.UUID(req.user_id), admin.id)
        return {"status": "approved", "api_key": raw_key, "message": "API key generated. This is the only time it will be shown."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/users/reject")
def reject_user(req: ApproveRequest, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        target = db.query(User).filter(User.id == uuid.UUID(req.user_id)).first()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        require_same_tenant(target.tenant, admin)
    finally:
        db.close()

    service = AuthService()
    try:
        service.reject_user(uuid.UUID(req.user_id))
        return {"status": "rejected"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/devices/pending")
def list_pending_devices(admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        devices = db.query(Device).filter(Device.status == "pending", Device.tenant == admin.tenant).all()
        return [{"id": str(d.id), "user_id": str(d.user_id), "device_name": d.device_name, "requested_at": d.requested_at} for d in devices]
    finally:
        db.close()

@router.post("/devices/approve")
def approve_device(req: DeviceActionRequest, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        target = db.query(Device).filter(Device.id == uuid.UUID(req.device_id)).first()
        if not target:
            raise HTTPException(status_code=404, detail="Device not found")
        require_same_tenant(target.tenant, admin)
    finally:
        db.close()

    service = AuthService()
    try:
        service.approve_device(uuid.UUID(req.device_id), admin.id)
        return {"status": "approved"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/devices/revoke")
def revoke_device(req: DeviceActionRequest, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        device = db.query(Device).filter(Device.id == uuid.UUID(req.device_id)).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        require_same_tenant(device.tenant, admin)
        device.status = "revoked"
        db.commit()
        return {"status": "revoked"}
    finally:
        db.close()

@router.post("/api-keys/revoke")
def revoke_api_key(key_id: str, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        key = db.query(APIKey).filter(APIKey.id == uuid.UUID(key_id)).first()
        if not key:
            raise HTTPException(status_code=404, detail="API Key not found")
        require_same_tenant(key.tenant, admin)
        key.revoked_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "revoked"}
    finally:
        db.close()
