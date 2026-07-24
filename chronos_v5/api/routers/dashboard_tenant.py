# chronos_v5/api/routers/dashboard_tenant.py
from fastapi import APIRouter, Depends, Query, Request
from chronos_v5.repositories.savings_repository import SavingsRepository
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.models import User
from chronos_v5.logger_setup import logger

router = APIRouter()

@router.get("/savings")
def get_savings(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user)
):
    tenant = current_user.tenant
    repo = SavingsRepository()
    summary = repo.get_savings_summary(tenant, days)
    breakdown = repo.get_daily_breakdown(tenant, days)
    return {
        "summary": summary,
        "daily_breakdown": breakdown
    }
