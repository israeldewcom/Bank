# chronos_v5/repositories/savings_repository.py
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import PnLAttribution
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from chronos_v5.config import Config

class SavingsRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_savings_summary(self, tenant: str, days: int = 30):
        cutoff = datetime.now() - timedelta(days=days)
        query = self.db.query(
            func.sum(PnLAttribution.amount_saved).label("total_savings"),
            func.count(PnLAttribution.id).label("trade_count")
        ).filter(
            and_(
                PnLAttribution.tenant == tenant,
                PnLAttribution.timestamp > cutoff
            )
        )
        result = query.first()
        total_savings = result.total_savings or 0.0
        trade_count = result.trade_count or 0
        fee = total_savings * Config.PERFORMANCE_FEE_PERCENT
        return {
            "tenant": tenant,
            "period_days": days,
            "total_savings": total_savings,
            "performance_fee": fee,
            "net_savings": total_savings - fee,
            "trade_count": trade_count
        }

    def get_daily_breakdown(self, tenant: str, days: int = 30):
        cutoff = datetime.now() - timedelta(days=days)
        results = self.db.query(
            func.date(PnLAttribution.timestamp).label("date"),
            func.sum(PnLAttribution.amount_saved).label("savings")
        ).filter(
            and_(
                PnLAttribution.tenant == tenant,
                PnLAttribution.timestamp > cutoff
            )
        ).group_by("date").order_by("date").all()
        return [{"date": r.date.isoformat(), "savings": r.savings or 0.0} for r in results]
