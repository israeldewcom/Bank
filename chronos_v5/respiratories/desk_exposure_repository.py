from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Trade

class DeskExposureRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get_desk_exposure(self, desk):
        trades = self.db.query(Trade).filter(Trade.desk == desk, Trade.status != "SETTLED").all()
        total = sum(t.notional for t in trades)
        return total
