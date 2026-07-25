# chronos_v5/repositories/desk_exposure_repository.py
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Trade
from chronos_v5.logger_setup import logger

class DeskExposureRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_desk_exposure(self, desk):
        try:
            trades = self.db.query(Trade).filter(Trade.desk == desk, Trade.status != "SETTLED").all()
            total = sum(t.notional for t in trades)
            return total
        except Exception as e:
            self.db.rollback()
            logger.error(f"get_desk_exposure failed: {e}")
            return 0
