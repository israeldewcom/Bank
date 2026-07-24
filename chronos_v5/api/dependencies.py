# chronos_v5/api/dependencies.py
from fastapi import Header, HTTPException
from chronos_v5.config import Config
from .auth_deps import (
    get_current_user,
    get_admin_user,
    get_tenant_from_request,
    get_tenant_from_auth
)

async def get_api_key(api_key: str = Header(..., alias="X-API-Key")):
    if api_key != Config.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

__all__ = [
    "get_api_key",
    "get_current_user",
    "get_admin_user",
    "get_tenant_from_request",
    "get_tenant_from_auth"
]
