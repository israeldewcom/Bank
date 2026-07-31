from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import Counterparty

class CounterpartyRepository:
    def __init__(self):
        self.db = SyncSessionLocal()

    def get(self, counterparty_id, tenant: str):
        return self.db.query(Counterparty).filter(
            Counterparty.id == counterparty_id,
            Counterparty.tenant == tenant,
        ).first()

    def update_risk(self, counterparty_id, risk_score, tenant: str):
        cp = self.get(counterparty_id, tenant)
        if cp:
            cp.risk_score = risk_score
            self.db.commit()
        return cp
