from fastapi import APIRouter, Depends
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Trade, RiskMetrics, PnLAttribution
from chronos_v5.api.dependencies import get_api_key
from datetime import datetime, timedelta
from sqlalchemy import func

router = APIRouter()

@router.get("/metrics", dependencies=[Depends(get_api_key)])
def dashboard_metrics():
    db = SyncSessionLocal()
    total_trades = db.query(Trade).count()
    pending = db.query(Trade).filter(Trade.status == "PENDING").count()
    recent_risk = db.query(RiskMetrics).order_by(RiskMetrics.timestamp.desc()).first()
    total_saved = db.query(func.sum(PnLAttribution.amount_saved)).filter(PnLAttribution.timestamp > datetime.now() - timedelta(days=30)).scalar() or 0
    db.close()
    return {
        "total_trades": total_trades,
        "pending_trades": pending,
        "last_risk": recent_risk,
        "savings_last_30d": total_saved
    }
