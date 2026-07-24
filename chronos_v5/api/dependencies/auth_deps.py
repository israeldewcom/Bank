# chronos_v5/api/dependencies/auth_deps.py
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from chronos_v5.config import Config
from chronos_v5.utils.jwt_utils import decode_jwt
from chronos_v5.services.auth_service import AuthService
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User
import uuid

security = HTTPBearer()

def get_tenant_from_request(request: Request) -> str:
    return request.headers.get(Config.TENANT_HEADER, Config.DEFAULT_TENANT)

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """JWT-based authentication – returns the user object."""
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
    # Attach tenant to request state for downstream use
    request.state.tenant = user.tenant
    return user

async def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "developer"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user

async def get_api_key_or_jwt(request: Request):
    """
    Dependency that checks either the legacy X-API-Key header (for old clients)
    OR the new JWT Bearer token. Returns the tenant from either.
    """
    # Check legacy API key first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        if api_key != Config.API_KEY:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key")
        tenant = request.headers.get(Config.TENANT_HEADER, Config.DEFAULT_TENANT)
        request.state.tenant = tenant
        request.state.auth_type = "api_key"
        return {"tenant": tenant, "user": None, "auth_type": "api_key"}
    # Fallback to JWT
    try:
        user = await get_current_user(request)
        request.state.auth_type = "jwt"
        return {"tenant": user.tenant, "user": user, "auth_type": "jwt"}
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No valid authentication provided")
