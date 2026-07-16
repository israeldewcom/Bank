from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Trade, PnLAttribution

class AuditRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_trade_audit(self, trade_id):
        trade = self.db.query(Trade).filter(Trade.id == trade_id).first()
        pnl = self.db.query(PnLAttribution).filter(PnLAttribution.trade_id == trade_id).all()
        return {"trade": trade, "pnl": pnl}
