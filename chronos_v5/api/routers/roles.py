# chronos_v5/api/routers/roles.py
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_limiter.depends import RateLimiter
from chronos_v5.api.dependencies import get_admin_user
from chronos_v5.models import User, Role
from chronos_v5.database import SyncSessionLocal
from chronos_v5.logger_setup import logger
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/admin/roles", tags=["Roles"])

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str] = []

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None

@router.get("/", dependencies=[Depends(RateLimiter(times=100, seconds=60))])
def list_roles(admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        roles = db.query(Role).filter(
            (Role.tenant_id == admin.tenant) | (Role.tenant_id.is_(None))
        ).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "permissions": r.permissions,
                "tenant_id": r.tenant_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in roles
        ]
    finally:
        db.close()

@router.post("/", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
def create_role(data: RoleCreate, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        existing = db.query(Role).filter(
            Role.name == data.name,
            (Role.tenant_id == admin.tenant) | (Role.tenant_id.is_(None))
        ).first()
        if existing:
            raise HTTPException(400, f"Role '{data.name}' already exists")

        role = Role(
            id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            permissions=data.permissions or [],
            tenant_id=admin.tenant,
            created_at=datetime.now(timezone.utc),
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        logger.info(f"Role created: {role.name} (tenant: {admin.tenant}) by admin {admin.id}")
        return {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "permissions": role.permissions,
            "tenant_id": role.tenant_id,
            "created_at": role.created_at.isoformat() if role.created_at else None,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create role: {e}")
        raise HTTPException(500, "Failed to create role")
    finally:
        db.close()

@router.get("/{role_id}", dependencies=[Depends(RateLimiter(times=100, seconds=60))])
def get_role(role_id: str, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(404, "Role not found")
        if role.tenant_id and role.tenant_id != admin.tenant:
            raise HTTPException(403, "Cannot access role from another tenant")
        return {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "permissions": role.permissions,
            "tenant_id": role.tenant_id,
            "created_at": role.created_at.isoformat() if role.created_at else None,
            "updated_at": role.updated_at.isoformat() if role.updated_at else None,
        }
    finally:
        db.close()

@router.put("/{role_id}", dependencies=[Depends(RateLimiter(times=20, seconds=60))])
def update_role(role_id: str, data: RoleUpdate, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(404, "Role not found")
        if role.tenant_id and role.tenant_id != admin.tenant:
            raise HTTPException(403, "Cannot modify role from another tenant")

        update_data = data.dict(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(role, key):
                setattr(role, key, value)
        role.updated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Role updated: {role_id} by admin {admin.id}")
        return {
            "status": "updated",
            "id": role.id,
            "name": role.name,
            "permissions": role.permissions,
        }
    finally:
        db.close()

@router.delete("/{role_id}", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
def delete_role(role_id: str, admin: User = Depends(get_admin_user)):
    db = SyncSessionLocal()
    try:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(404, "Role not found")
        if role.tenant_id and role.tenant_id != admin.tenant:
            raise HTTPException(403, "Cannot delete role from another tenant")
        db.delete(role)
        db.commit()
        logger.info(f"Role deleted: {role_id} by admin {admin.id}")
        return {"status": "deleted"}
    finally:
        db.close()
