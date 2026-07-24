# chronos_v5/api/routers/tenant_config.py
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from chronos_v5.services.tenant_config_service import TenantConfigService
from chronos_v5.api.dependencies.auth_deps import get_api_key_or_jwt

router = APIRouter()

class ConfigUpdateRequest(BaseModel):
    performance_fee_percent: Optional[float] = None
    bloomberg_api_key: Optional[str] = None
    reuters_api_key: Optional[str] = None
    alpha_vantage_key: Optional[str] = None
    nibss_api_key: Optional[str] = None
    cbn_openapi_url: Optional[str] = None
    ngx_api_url: Optional[str] = None
    use_global_model: Optional[bool] = None
    alpha_strategy_type: Optional[str] = None

@router.get("/")
def get_config(request: Request):
    auth = request.state
    tenant = auth.tenant if hasattr(auth, "tenant") else "default"
    service = TenantConfigService()
    config = service.get_config(tenant)
    # Mask sensitive fields
    for key in ["bloomberg_api_key", "reuters_api_key", "alpha_vantage_key", "nibss_api_key"]:
        if config.get(key):
            config[key] = "********"  # show only masked
    return config

@router.put("/")
def update_config(req: ConfigUpdateRequest, request: Request):
    # Only admin or developer can update config
    auth = request.state
    if not hasattr(auth, "auth_type") or auth.auth_type != "jwt":
        raise HTTPException(status_code=403, detail="JWT authentication required")
    # Check role from JWT – we can fetch from user object if we extended get_api_key_or_jwt to include user
    # For simplicity, we rely on the dependency to have set auth.user
    if hasattr(auth, "user") and auth.user and auth.user.role in ("admin", "developer"):
        tenant = auth.tenant
        service = TenantConfigService()
        updates = req.dict(exclude_unset=True)
        service.update_config(tenant, updates)
        return {"status": "updated"}
    raise HTTPException(status_code=403, detail="Insufficient permissions")
