from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Counterparty

class CounterpartyRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get(self, counterparty_id):
        return self.db.query(Counterparty).filter(Counterparty.id == counterparty_id).first()

    def update_risk(self, counterparty_id, risk_score):
        cp = self.get(counterparty_id)
        if cp:
            cp.risk_score = risk_score
            self.db.commit()
        return cp
