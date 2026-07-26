from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Trade, PnLAttribution

class AuditRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_trade_audit(self, trade_id, tenant: str = None):
        trade_q = self.db.query(Trade).filter(Trade.id == trade_id)
        pnl_q = self.db.query(PnLAttribution).filter(PnLAttribution.trade_id == trade_id)
        if tenant is not None:
            trade_q = trade_q.filter(Trade.tenant == tenant)
            pnl_q = pnl_q.filter(PnLAttribution.tenant == tenant)
        trade = trade_q.first()
        pnl = pnl_q.all()
        return {"trade": trade, "pnl": pnl}
