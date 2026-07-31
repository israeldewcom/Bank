# chronos_v5/api/dependencies.py
# SINGLE CANONICAL AUTH MODULE — delete chronos_v5/api/auth_deps.py and the
# chronos_v5/api/dependencies/ package directory entirely. Every router in
# the codebase imports from this one file only: `from chronos_v5.api.dependencies import ...`
from fastapi import Header, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone
from chronos_v5.config import Config
from chronos_v5.utils.jwt_utils import decode_jwt
from chronos_v5.services.auth_service import AuthService
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User

security = HTTPBearer(auto_error=False)

async def get_api_key(api_key: str = Header(..., alias="X-API-Key")):
    if api_key != Config.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

def get_tenant_for_registration(request: Request) -> str:
    """
    Header-derived tenant. ONLY valid to use on unauthenticated endpoints where
    no user identity exists yet (e.g. /auth/register). Never use this on any
    route that also depends on get_current_user / get_admin_user — an
    authenticated caller must always be scoped by their OWN user.tenant
    (see get_tenant_from_auth below), never by a header they control.
    """
    return request.headers.get(Config.TENANT_HEADER, Config.DEFAULT_TENANT)

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    api_key = request.headers.get("X-API-Key")
    if api_key:
        auth_service = AuthService()
        user, key = auth_service.validate_api_key(api_key)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not active")
        if key:
            key.last_used_at = datetime.now(timezone.utc)
            auth_service.db.commit()
        request.state.tenant = user.tenant
        request.state.auth_type = "api_key"
        return user

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No authentication provided")
    token = credentials.credentials
    payload = decode_jwt(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    db = SyncSessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not active")
    request.state.tenant = user.tenant
    request.state.auth_type = "jwt"
    return user

async def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "developer"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user

async def get_tenant_from_auth(request: Request, user: User = Depends(get_current_user)):
    return user.tenant

def require_same_tenant(target_tenant: str, actor: User):
    """
    Call this inside any admin-action endpoint that operates on a target
    record (user, device, api key, etc.) looked up by id. Raises 403 if the
    target record's tenant does not match the acting admin's own tenant.
    This is what stops a tenant-A admin from approving/revoking/reading
    tenant-B's users, devices, or keys.
    """
    if target_tenant != actor.tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot act on a resource outside your tenant")

__all__ = [
    "get_api_key",
    "get_tenant_for_registration",
    "get_current_user",
    "get_admin_user",
    "get_tenant_from_auth",
    "require_same_tenant",
]
