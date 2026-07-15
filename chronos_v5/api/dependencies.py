from fastapi import Header, HTTPException
from chronos_v5.config import Config

async def get_api_key(api_key: str = Header(..., alias="X-API-Key")):
    if api_key != Config.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

async def get_tenant(tenant: str = Header(None, alias=Config.TENANT_HEADER)):
    return tenant or Config.DEFAULT_TENANT
