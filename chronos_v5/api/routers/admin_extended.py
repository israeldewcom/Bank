# chronos_v5/api/routers/admin_extended.py
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from chronos_v5.api.dependencies import get_admin_user, get_current_user, require_same_tenant
from chronos_v5.models import User
from chronos_v5.services.user_service import UserService
from chronos_v5.services.device_service import DeviceService
from chronos_v5.services.tenant_service import TenantService
from chronos_v5.logger_setup import logger

router = APIRouter(prefix="/admin", tags=["Admin Extended"])

# ========== SCHEMAS ==========
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: Optional[str] = "user"

class TenantCreate(BaseModel):
    name: str
    config: Optional[dict] = None

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    config: Optional[dict] = None

# ========== USERS ==========
@router.get("/users")
def list_users(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_admin_user)
):
    service = UserService()
    try:
        users = service.get_all_users(tenant=admin.tenant, limit=limit, offset=offset)
        return [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "status": u.status,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    finally:
        service.close()

@router.get("/users/{user_id}")
def get_user(user_id: str, admin: User = Depends(get_admin_user)):
    service = UserService()
    try:
        user = service.get_user(user_id)
        if not user:
            raise HTTPException(404, "User not found")
        require_same_tenant(user.tenant, admin)
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "status": user.status,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
    finally:
        service.close()

@router.put("/users/{user_id}")
def update_user(user_id: str, data: UserUpdate, admin: User = Depends(get_admin_user)):
    service = UserService()
    try:
        user = service.get_user(user_id)
        if not user:
            raise HTTPException(404, "User not found")
        require_same_tenant(user.tenant, admin)
        updated = service.update_user(user_id, data.dict(exclude_unset=True))
        return {"status": "updated", "user_id": user_id}
    finally:
        service.close()

@router.delete("/users/{user_id}")
def delete_user(user_id: str, admin: User = Depends(get_admin_user)):
    service = UserService()
    try:
        user = service.get_user(user_id)
        if not user:
            raise HTTPException(404, "User not found")
        require_same_tenant(user.tenant, admin)
        service.delete_user(user_id)
        return {"status": "deleted"}
    finally:
        service.close()

# ========== DEVICES ==========
@router.get("/devices")
def list_devices(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_admin_user)
):
    service = DeviceService()
    try:
        devices = service.get_all_devices(tenant=admin.tenant, limit=limit, offset=offset)
        return [
            {
                "id": d.id,
                "user_id": d.user_id,
                "device_name": d.device_name,
                "device_fingerprint": d.device_fingerprint,
                "status": d.status,
                "last_used_at": d.last_used_at.isoformat() if d.last_used_at else None,
                "requested_at": d.requested_at.isoformat() if d.requested_at else None,
            }
            for d in devices
        ]
    finally:
        service.close()

@router.delete("/devices/{device_id}")
def delete_device(device_id: str, admin: User = Depends(get_admin_user)):
    service = DeviceService()
    try:
        device = service.get_device(device_id)
        if not device:
            raise HTTPException(404, "Device not found")
        require_same_tenant(device.tenant, admin)
        service.delete_device(device_id)
        return {"status": "deleted"}
    finally:
        service.close()

# ========== TENANTS ==========
@router.get("/tenants")
def list_tenants(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_admin_user)
):
    service = TenantService()
    try:
        tenants = service.get_all_tenants(limit, offset)
        return [
            {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "config": t.config,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tenants
        ]
    finally:
        service.close()

@router.post("/tenants")
def create_tenant(data: TenantCreate, admin: User = Depends(get_admin_user)):
    service = TenantService()
    try:
        tenant = service.create_tenant(data.name, data.config)
        return {"id": tenant.id, "name": tenant.name, "status": tenant.status}
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        service.close()

@router.put("/tenants/{tenant_id}")
def update_tenant(tenant_id: str, data: TenantUpdate, admin: User = Depends(get_admin_user)):
    service = TenantService()
    try:
        tenant = service.update_tenant(tenant_id, data.dict(exclude_unset=True))
        return {"status": "updated", "id": tenant.id}
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        service.close()

@router.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: str, admin: User = Depends(get_admin_user)):
    service = TenantService()
    try:
        service.delete_tenant(tenant_id)
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        service.close()
