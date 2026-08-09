# chronos_v5/api/dependencies.py
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
    """
    Validate API key for service-to-service authentication.
    """
    if api_key != Config.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key


def get_tenant_for_registration(request: Request) -> str:
    """
    Header-derived tenant for registration only.
    ONLY valid on unauthenticated endpoints like /auth/register.
    Never use on authenticated routes.
    """
    return request.headers.get(Config.TENANT_HEADER, Config.DEFAULT_TENANT)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get the current authenticated user from JWT or API key.
    This is the primary authentication dependency for all protected routes.
    """
    api_key = request.headers.get("X-API-Key")

    # Try API key authentication first
    if api_key:
        auth_service = AuthService()
        try:
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
        except Exception as e:
            auth_service.db.rollback()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
        finally:
            auth_service.db.close()

    # Then try JWT token
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No authentication provided")

    token = credentials.credentials
    payload = decode_jwt(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # Check token revocation
    jti = payload.get("jti")
    auth_service = AuthService()
    if auth_service.is_token_revoked(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    db = SyncSessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not active")
        request.state.tenant = user.tenant
        request.state.auth_type = "jwt"
        request.state.jwt_token = token
        return user
    finally:
        db.close()


async def get_admin_user(current_user: User = Depends(get_current_user)):
    """
    Require admin role for the current user.
    """
    if current_user.role not in ("admin", "developer"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user


async def get_developer_user(current_user: User = Depends(get_current_user)):
    """
    Require developer role (platform admin) for system-wide operations.
    """
    if current_user.role != "developer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Developer privileges required")
    return current_user


async def get_tenant_from_auth(request: Request, user: User = Depends(get_current_user)):
    """
    Get the tenant from the authenticated user.
    Use this instead of header-based tenant for authenticated routes.
    """
    return user.tenant


def require_same_tenant(target_tenant: str, actor: User):
    """
    Enforce that the actor (admin/user) can only act on resources
    belonging to their own tenant.
    Raises 403 if the target tenant differs.
    """
    if target_tenant != actor.tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot act on a resource outside your tenant"
        )


def require_tenant_match(target_tenant: str, actor_tenant: str):
    """
    Simple tenant match check without a User object.
    Useful for internal checks where you don't have the full User.
    """
    if target_tenant != actor_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant mismatch"
        )


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """
    Alias for get_current_user with active check already included.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")
    return current_user


async def get_current_tenant(request: Request, user: User = Depends(get_current_user)):
    """
    Get the current tenant from the authenticated user.
    Also validates that the header tenant matches the user tenant (if header is provided).
    """
    header_tenant = request.headers.get(Config.TENANT_HEADER)
    if header_tenant and header_tenant != user.tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant header does not match authenticated user's tenant"
        )
    return user.tenant


# Export all dependencies
__all__ = [
    "get_api_key",
    "get_tenant_for_registration",
    "get_current_user",
    "get_admin_user",
    "get_developer_user",
    "get_tenant_from_auth",
    "require_same_tenant",
    "require_tenant_match",
    "get_current_active_user",
    "get_current_tenant",
]
