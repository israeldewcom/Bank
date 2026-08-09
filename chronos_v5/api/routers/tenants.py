# chronos_v5/api/routers/tenants.py
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel
from typing import Optional, List
from chronos_v5.api.dependencies import get_admin_user, get_current_user, require_same_tenant
from chronos_v5.models import User
from chronos_v5.services.tenant_service import TenantService
from chronos_v5.logger_setup import logger

router = APIRouter(prefix="/admin/tenants", tags=["Tenants"])


class TenantCreate(BaseModel):
    name: str
    config: Optional[dict] = None


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None  # active, pending, suspended
    config: Optional[dict] = None


@router.get("/", dependencies=[Depends(RateLimiter(times=100, seconds=60))])
def list_tenants(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    include_config: bool = Query(False),
    admin: User = Depends(get_admin_user)
):
    """
    List all tenants. Admin only.
    """
    service = TenantService()
    try:
        tenants = service.get_all_tenants(limit, offset)
        result = []
        for t in tenants:
            tenant_data = {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            if include_config:
                tenant_data["config"] = t.config
            result.append(tenant_data)
        return {
            "tenants": result,
            "count": len(result),
            "limit": limit,
            "offset": offset
        }
    finally:
        service.close()


@router.get("/{tenant_id}", dependencies=[Depends(RateLimiter(times=100, seconds=60))])
def get_tenant(
    tenant_id: str,
    include_config: bool = Query(False),
    admin: User = Depends(get_admin_user)
):
    """
    Get a specific tenant by ID. Admin only.
    """
    service = TenantService()
    try:
        tenant = service.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(404, "Tenant not found")

        result = {
            "id": tenant.id,
            "name": tenant.name,
            "status": tenant.status,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
            "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
        }
        if include_config:
            result["config"] = tenant.config
        return result
    finally:
        service.close()


@router.get("/by-name/{name}", dependencies=[Depends(RateLimiter(times=100, seconds=60))])
def get_tenant_by_name(
    name: str,
    include_config: bool = Query(False),
    admin: User = Depends(get_admin_user)
):
    """
    Get a tenant by name. Admin only.
    """
    service = TenantService()
    try:
        tenant = service.repo.get_by_name(name)
        if not tenant:
            raise HTTPException(404, "Tenant not found")

        result = {
            "id": tenant.id,
            "name": tenant.name,
            "status": tenant.status,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
            "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
        }
        if include_config:
            result["config"] = tenant.config
        return result
    finally:
        service.close()


@router.post("/", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
def create_tenant(data: TenantCreate, admin: User = Depends(get_admin_user)):
    """
    Create a new tenant. Admin only.
    """
    service = TenantService()
    try:
        tenant = service.create_tenant(data.name, data.config or {})
        logger.info(f"Tenant created: {tenant.id} ({tenant.name}) by admin {admin.id}")
        return {
            "id": tenant.id,
            "name": tenant.name,
            "status": tenant.status,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Failed to create tenant: {e}")
        raise HTTPException(500, "Failed to create tenant")
    finally:
        service.close()


@router.put("/{tenant_id}", dependencies=[Depends(RateLimiter(times=20, seconds=60))])
def update_tenant(
    tenant_id: str,
    data: TenantUpdate,
    admin: User = Depends(get_admin_user)
):
    """
    Update a tenant. Admin only.
    """
    service = TenantService()
    try:
        update_data = data.dict(exclude_unset=True)
        tenant = service.update_tenant(tenant_id, update_data)
        logger.info(f"Tenant updated: {tenant_id} by admin {admin.id}")
        return {
            "id": tenant.id,
            "name": tenant.name,
            "status": tenant.status,
            "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Failed to update tenant {tenant_id}: {e}")
        raise HTTPException(500, "Failed to update tenant")
    finally:
        service.close()


@router.delete("/{tenant_id}", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
def delete_tenant(
    tenant_id: str,
    admin: User = Depends(get_admin_user)
):
    """
    Delete a tenant. Admin only. This is permanent.
    """
    service = TenantService()
    try:
        # Get tenant first to log details
        tenant = service.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(404, "Tenant not found")

        service.delete_tenant(tenant_id)
        logger.info(f"Tenant deleted: {tenant_id} ({tenant.name}) by admin {admin.id}")
        return {"status": "deleted", "id": tenant_id}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Failed to delete tenant {tenant_id}: {e}")
        raise HTTPException(500, "Failed to delete tenant")
    finally:
        service.close()


@router.post("/{tenant_id}/activate", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
def activate_tenant(
    tenant_id: str,
    admin: User = Depends(get_admin_user)
):
    """
    Activate a tenant (set status to active). Admin only.
    """
    service = TenantService()
    try:
        tenant = service.update_tenant(tenant_id, {"status": "active"})
        if not tenant:
            raise HTTPException(404, "Tenant not found")
        logger.info(f"Tenant activated: {tenant_id} by admin {admin.id}")
        return {"status": "active", "id": tenant_id}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Failed to activate tenant {tenant_id}: {e}")
        raise HTTPException(500, "Failed to activate tenant")
    finally:
        service.close()


@router.post("/{tenant_id}/suspend", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
def suspend_tenant(
    tenant_id: str,
    admin: User = Depends(get_admin_user)
):
    """
    Suspend a tenant (set status to suspended). Admin only.
    """
    service = TenantService()
    try:
        tenant = service.update_tenant(tenant_id, {"status": "suspended"})
        if not tenant:
            raise HTTPException(404, "Tenant not found")
        logger.info(f"Tenant suspended: {tenant_id} by admin {admin.id}")
        return {"status": "suspended", "id": tenant_id}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Failed to suspend tenant {tenant_id}: {e}")
        raise HTTPException(500, "Failed to suspend tenant")
    finally:
        service.close()
