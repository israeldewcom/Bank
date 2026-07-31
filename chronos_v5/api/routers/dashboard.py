# chronos_v5/api/routers/dashboard.py
# SECURITY FIX: this endpoint used to be gated only by get_api_key, a single
# static secret shared platform-wide with no tenant concept, and its queries
# had no tenant filter at all — any holder of that one key saw total trade
# counts, risk metrics, and P&L savings across every tenant on the system.
# Now gated by get_current_user (real per-user auth) and every query is
# scoped to current_user.tenant.
from fastapi import APIRouter, Depends
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Trade, RiskMetrics, PnLAttribution, User
from chronos_v5.api.dependencies import get_current_user
from datetime import datetime, timedelta
from sqlalchemy import func

router = APIRouter()

@router.get("/metrics")
def dashboard_metrics(current_user: User = Depends(get_current_user)):
    tenant = current_user.tenant
    db = SyncSessionLocal()
    try:
        total_trades = db.query(Trade).filter(Trade.tenant == tenant).count()
        pending = db.query(Trade).filter(Trade.tenant == tenant, Trade.status == "PENDING").count()
        recent_risk = (
            db.query(RiskMetrics)
            .filter(RiskMetrics.tenant == tenant)
            .order_by(RiskMetrics.timestamp.desc())
            .first()
        )
        total_saved = (
            db.query(func.sum(PnLAttribution.amount_saved))
            .filter(
                PnLAttribution.tenant == tenant,
                PnLAttribution.timestamp > datetime.now() - timedelta(days=30),
            )
            .scalar()
            or 0
        )
        return {
            "total_trades": total_trades,
            "pending_trades": pending,
            "last_risk": recent_risk,
            "savings_last_30d": total_saved
        }
    finally:
        db.close()
