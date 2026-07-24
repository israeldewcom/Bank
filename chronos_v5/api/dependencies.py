# chronos_v5/api/dependencies.py
from fastapi import Header, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone
from chronos_v5.config import Config
from chronos_v5.utils.jwt_utils import decode_jwt
from chronos_v5.services.auth_service import AuthService
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User
import uuid

security = HTTPBearer(auto_error=False)

# ----------------------
# Legacy API key check (used by some old routes)
# ----------------------
async def get_api_key(api_key: str = Header(..., alias="X-API-Key")):
    if api_key != Config.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

# ----------------------
# Tenant extraction from request header
# ----------------------
def get_tenant_from_request(request: Request) -> str:
    return request.headers.get(Config.TENANT_HEADER, Config.DEFAULT_TENANT)

# ----------------------
# Main authentication: API key (new) or JWT
# ----------------------
async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # 1. Try API key (new, database-backed)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        auth_service = AuthService()
        user, key = auth_service.validate_api_key(api_key)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
        if user.status != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not approved")
        if key:
            key.last_used_at = datetime.now(timezone.utc)
            auth_service.db.commit()
        request.state.tenant = user.tenant
        request.state.auth_type = "api_key"
        return user

    # 2. Fallback to JWT (Bearer token)
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
    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    db.close()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status != "approved":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account not approved")
    request.state.tenant = user.tenant
    request.state.auth_type = "jwt"
    return user

# ----------------------
# Admin/developer privilege check
# ----------------------
async def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "developer"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user

# ----------------------
# Get tenant from authenticated user
# ----------------------
async def get_tenant_from_auth(request: Request, user: User = Depends(get_current_user)):
    return user.tenant

# Explicitly export all these functions so that `from chronos_v5.api.dependencies import ...` works
__all__ = [
    "get_api_key",
    "get_tenant_from_request",
    "get_current_user",
    "get_admin_user",
    "get_tenant_from_auth"
]
