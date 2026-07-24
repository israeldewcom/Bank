# chronos_v5/api/routers/dashboard_tenant.py
from fastapi import APIRouter, Depends, Query, Request
from chronos_v5.repositories.savings_repository import SavingsRepository
from chronos_v5.api.dependencies.auth_deps import get_api_key_or_jwt
from chronos_v5.logger_setup import logger

router = APIRouter()

@router.get("/savings")
def get_savings(request: Request, days: int = Query(30, ge=1, le=365)):
    auth = request.state
    tenant = auth.tenant if hasattr(auth, "tenant") else "default"
    repo = SavingsRepository()
    summary = repo.get_savings_summary(tenant, days)
    breakdown = repo.get_daily_breakdown(tenant, days)
    return {
        "summary": summary,
        "daily_breakdown": breakdown
    }
