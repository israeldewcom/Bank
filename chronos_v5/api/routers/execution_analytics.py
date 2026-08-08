# chronos_v5/api/routers/execution_analytics.py
from fastapi import APIRouter, Depends, HTTPException, Query
from chronos_v5.api.dependencies import get_current_user
from chronos_v5.models import User, ExecutionOrder
from chronos_v5.database import SyncSessionLocal
from sqlalchemy import func, and_
from datetime import datetime, timedelta

router = APIRouter(prefix="/execution", tags=["Execution Analytics"])

@router.get("/analytics")
def get_execution_analytics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user)
):
    db = SyncSessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=days)
        orders = db.query(ExecutionOrder).filter(
            ExecutionOrder.tenant == current_user.tenant,
            ExecutionOrder.sent_at >= cutoff
        ).all()

        total = len(orders)
        filled = sum(1 for o in orders if o.status == 'FILLED')
        failed = sum(1 for o in orders if o.status == 'FAILED')
        pending = sum(1 for o in orders if o.status in ('PENDING', 'SENT'))

        fill_times = []
        for o in orders:
            if o.filled_at and o.sent_at:
                fill_times.append((o.filled_at - o.sent_at).total_seconds())
        avg_fill_time = sum(fill_times)/len(fill_times) if fill_times else None

        slippage = 0.0  # Placeholder

        return {
            "total_orders": total,
            "filled": filled,
            "failed": failed,
            "pending": pending,
            "fill_rate": filled / total if total > 0 else 0,
            "avg_fill_time_seconds": avg_fill_time,
            "slippage_bps": slippage,
            "period_days": days,
        }
    finally:
        db.close()
