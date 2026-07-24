# chronos_v5/api/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
import uuid
from datetime import datetime, timezone
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User, Device, APIKey
from chronos_v5.services.auth_service import AuthService
from chronos_v5.api.dependencies import get_admin_user, get_current_user
from chronos_v5.logger_setup import logger

router = APIRouter()

class ApproveRequest(BaseModel):
    user_id: str

class DeviceActionRequest(BaseModel):
    device_id: str

@router.get("/users/pending")
def list_pending_users(admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    users = db.query(User).filter(User.status == "pending").all()
    db.close()
    return [{"id": str(u.id), "email": u.email, "full_name": u.full_name, "tenant": u.tenant, "created_at": u.created_at} for u in users]

@router.post("/users/approve")
def approve_user(req: ApproveRequest, admin: User = Depends(get_admin_user)):
    service = AuthService()
    try:
        raw_key = service.approve_user(uuid.UUID(req.user_id), admin.id)
        return {"status": "approved", "api_key": raw_key, "message": "API key generated. This is the only time it will be shown."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/users/reject")
def reject_user(req: ApproveRequest, admin: User = Depends(get_admin_user)):
    service = AuthService()
    try:
        service.reject_user(uuid.UUID(req.user_id))
        return {"status": "rejected"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/devices/pending")
def list_pending_devices(admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    devices = db.query(Device).filter(Device.status == "pending").all()
    db.close()
    return [{"id": str(d.id), "user_id": str(d.user_id), "device_name": d.device_name, "requested_at": d.requested_at} for d in devices]

@router.post("/devices/approve")
def approve_device(req: DeviceActionRequest, admin: User = Depends(get_admin_user)):
    service = AuthService()
    try:
        service.approve_device(uuid.UUID(req.device_id), admin.id)
        return {"status": "approved"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/devices/revoke")
def revoke_device(req: DeviceActionRequest, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    device = db.query(Device).filter(Device.id == uuid.UUID(req.device_id)).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.status = "revoked"
    db.commit()
    db.close()
    return {"status": "revoked"}

@router.post("/api-keys/revoke")
def revoke_api_key(key_id: str, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    key = db.query(APIKey).filter(APIKey.id == uuid.UUID(key_id)).first()
    if not key:
        raise HTTPException(status_code=404, detail="API Key not found")
    key.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.close()
    return {"status": "revoked"}
