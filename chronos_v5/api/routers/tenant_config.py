# chronos_v5/api/routers/tenant_config.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from chronos_v5.services.tenant_config_service import TenantConfigService
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.models import User

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
def get_config(current_user: User = Depends(get_current_user)):
    service = TenantConfigService()
    config = service.get_config(current_user.tenant)
    for key in ["bloomberg_api_key", "reuters_api_key", "alpha_vantage_key", "nibss_api_key"]:
        if config.get(key):
            config[key] = "********"
    return config

@router.put("/")
def update_config(
    req: ConfigUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ("admin", "developer"):
        raise HTTPException(status_code=403, detail="Insufficient permissions – admin or developer required")
    service = TenantConfigService()
    updates = req.dict(exclude_unset=True)
    service.update_config(current_user.tenant, updates)
    return {"status": "updated"}
