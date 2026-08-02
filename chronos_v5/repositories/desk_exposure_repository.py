# chronos_v5/repositories/desk_exposure_repository.py — full corrected file
# chronos_v5/repositories/desk_exposure_repository.py
# SECURITY FIX: tenant was optional (default None), silently falling back to
# an unscoped query across every tenant's trades if a caller ever omitted
# it — the same class of bug found and fixed in trade_repository.insert().
# All current callers (services/predictor.py) already pass tenant
# explicitly; this closes the hole for any future caller that doesn't.
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Trade
from chronos_v5.logger_setup import logger

class DeskExposureRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_desk_exposure(self, desk, tenant: str):
        if not tenant:
            raise ValueError("tenant is required for get_desk_exposure() — "
                              "refusing to run an unscoped cross-tenant query.")
        try:
            q = self.db.query(Trade).filter(
                Trade.desk == desk, Trade.status != "SETTLED", Trade.tenant == tenant
            )
            trades = q.all()
            total = sum(t.notional for t in trades)
            return total
        except Exception as e:
            self.db.rollback()
            logger.error(f"get_desk_exposure failed: {e}")
            return 0
