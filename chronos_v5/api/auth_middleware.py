from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User
from chronos_v5.config import Config
from datetime import datetime, timezone
import re

class AuthMiddleware(BaseHTTPMiddleware):
    # Paths that do not require authentication
    EXEMPT_PATHS = [
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/admin/login",
        "/admin/register",  # optional
        "/static",
    ]

    async def dispatch(self, request: Request, call_next):
        # Allow OPTIONS requests (preflight) without authentication
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip middleware for exempt paths
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)

        # Check for API key or user session?
        api_key = request.headers.get("X-API-Key")
        if api_key == Config.API_KEY:
            # Master key allowed, skip user check
            return await call_next(request)

        # If no master key, we expect a tenant header and a user session
        tenant = request.headers.get(Config.TENANT_HEADER)
        if tenant:
            db = SyncSessionLocal()
            user = db.query(User).filter(User.tenant == tenant, User.is_active == True).first()
            db.close()
            if user:
                if user.trial_expiry and datetime.now(timezone.utc) > user.trial_expiry:
                    return JSONResponse(status_code=403, content={"detail": "Trial expired. Please upgrade."})
                return await call_next(request)

        return JSONResponse(status_code=401, content={"detail": "Authentication required"})
